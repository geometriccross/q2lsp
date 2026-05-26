import * as path from 'path';
import * as vscode from 'vscode';
import { type LanguageClient } from 'vscode-languageclient/node';
import {
	DEFAULT_PATH_CANDIDATES,
	buildInterpreterCandidates,
	type InterpreterCandidate,
} from './interpreterSources';
import { isAbsolutePath } from './interpreterPath';
import {
	buildInterpreterPathNotAbsoluteMessage,
	buildMissingInterpreterMessage,
	formatOutputSnippet,
} from './interpreterMessages';
import { resolveQ2lspConfig } from './config';
import { VALIDATION_TIMEOUT_MS, execFileForValidation, type ValidationResult, validateInterpreter } from './interpreter';
import { startQ2lspClient, stopQ2lspClient } from './client';
import {
	manageWorkspaceTrust,
	selectInterpreterCandidate,
	showDiagnoseMessage,
	showValidationError,
} from './diagnosis';
import {
	executeQiimeRunCommand,
	formatQiimeRunCommandTokens,
	resolveQiimeRunTerminal,
	toQiimeRunCommandPayload,
} from './runCommand';
import { openSetupWizard } from './setupWizard/index';
import { resolveConfiguredPythonInterpreter, resolveInterpreter } from './interpreter_resolver';

let client: LanguageClient | undefined;
let outputChannel: vscode.OutputChannel | undefined;

const getUnsupportedPlatformMessage = (platform: NodeJS.Platform): string | undefined => {
	if (platform !== 'win32') {
		return undefined;
	}

	return "q2lsp doesn't run on native Windows. Use WSL or Remote Linux/macOS.";
};

const shouldRestartOnConfigChange = (affectsConfiguration: (section: string) => boolean): boolean => {
	return affectsConfiguration('q2lsp.interpreterPath') || affectsConfiguration('q2lsp.serverEnv');
};

export async function activate(context: vscode.ExtensionContext) {
	outputChannel = vscode.window.createOutputChannel('q2lsp');
	context.subscriptions.push(outputChannel);

	const platformMessage = getUnsupportedPlatformMessage(process.platform);
	if (platformMessage) {
		outputChannel.appendLine(platformMessage);
		vscode.window.showErrorMessage(platformMessage);
		return;
	}

	context.subscriptions.push(
		vscode.commands.registerCommand('q2lsp.restartServer', async () => {
			await restartClient(context);
		})
	);

	context.subscriptions.push(
		vscode.commands.registerCommand('q2lsp.showServerLog', () => {
			outputChannel?.show(true);
		})
	);

	context.subscriptions.push(
		vscode.commands.registerCommand('q2lsp.diagnoseEnvironment', async () => {
			await diagnoseEnvironment(context);
		})
	);

	context.subscriptions.push(
		vscode.commands.registerCommand('q2lsp.openSetupWizard', async () => {
			const activeDocument = vscode.window.activeTextEditor?.document;
			const { interpreterPath: normalizedInterpreter } = resolveQ2lspConfig(activeDocument);
			const pythonExtensionInterpreter = normalizedInterpreter
				? undefined
				: await resolveConfiguredPythonInterpreter(outputChannel);
			openSetupWizard({
				context,
				outputChannel,
				interpreterPath: normalizedInterpreter ?? pythonExtensionInterpreter,
			});
		})
	);

	context.subscriptions.push(
		vscode.commands.registerCommand('q2lsp.runCommand', (payload: unknown) => {
			const commandPayload = toQiimeRunCommandPayload(payload);
			if (!commandPayload) {
				vscode.window.showErrorMessage('q2lsp.runCommand received an invalid command payload.');
				return;
			}

			outputChannel?.appendLine(
				`QIIME command tokens from ${commandPayload.uri}: ${formatQiimeRunCommandTokens(commandPayload)}`
			);
			const terminal = resolveQiimeRunTerminal(
				vscode.window.activeTerminal,
				vscode.window.terminals,
				() => vscode.window.createTerminal('q2lsp')
			);
			executeQiimeRunCommand(commandPayload, terminal);
			outputChannel?.show(true);
		})
	);

	context.subscriptions.push(
		vscode.workspace.onDidChangeConfiguration(async (event) => {
			if (shouldRestartOnConfigChange((section) => event.affectsConfiguration(section))) {
				await restartClient(context);
			}
		})
	);

	await startClient(context);
}

export async function deactivate() {
	await stopClient();
}

const restartClient = async (context: vscode.ExtensionContext): Promise<void> => {
	await stopClient();
	await startClient(context);
};

const stopClient = async (): Promise<void> => {
	if (!client) {
		return;
	}

	try {
		await stopQ2lspClient(client);
	} finally {
		client = undefined;
	}
};

const startClient = async (context: vscode.ExtensionContext): Promise<void> => {
	const activeDocument = vscode.window.activeTextEditor?.document;
	const { interpreterPath: normalizedInterpreter, serverEnvOverrides } = resolveQ2lspConfig(activeDocument);
	const resolvedInterpreter = await resolveInterpreter({
		context,
		outputChannel,
		config: { interpreterPath: normalizedInterpreter, serverEnv: serverEnvOverrides },
	});
	if (!resolvedInterpreter) {
		return;
	}

	const cwd = resolveServerCwd(activeDocument);
	const startedClient = await startQ2lspClient({
		interpreterPath: resolvedInterpreter.path,
		cwd,
		serverEnv: serverEnvOverrides,
		outputChannel,
	});

	client = startedClient;
	context.subscriptions.push(client);
	outputChannel?.appendLine(`Started q2lsp using ${resolvedInterpreter.path}.`);
};

const resolveServerCwd = (activeDocument: vscode.TextDocument | undefined): string | undefined => {
	const activeShellscriptDocument =
		activeDocument && activeDocument.languageId === 'shellscript' && activeDocument.uri.scheme === 'file'
			? activeDocument
			: undefined;
	if (activeShellscriptDocument) {
		const folder = vscode.workspace.getWorkspaceFolder(activeShellscriptDocument.uri);
		if (folder?.uri.scheme === 'file') {
			return folder.uri.fsPath;
		}
	}

	const fallbackWorkspace = vscode.workspace.workspaceFolders?.[0];
	if (fallbackWorkspace?.uri.scheme === 'file') {
		return fallbackWorkspace.uri.fsPath;
	}

	if (activeShellscriptDocument) {
		return path.dirname(activeShellscriptDocument.uri.fsPath);
	}

	return undefined;
};

const appendValidationReport = (candidate: InterpreterCandidate, validation: ValidationResult): void => {
	outputChannel?.appendLine('q2lsp diagnose report:');
	outputChannel?.appendLine(`Candidate: ${candidate.path} (${candidate.source})`);
	outputChannel?.appendLine(`Reported executable: ${validation.details?.executable ?? 'unknown'}`);
	outputChannel?.appendLine(
		`Missing modules: ${validation.missingModules?.length ? validation.missingModules.join(', ') : 'none'}`
	);
	outputChannel?.appendLine(`stdout: ${formatOutputSnippet(validation.stdout)}`);
	outputChannel?.appendLine(`stderr: ${formatOutputSnippet(validation.stderr)}`);
};

const diagnoseEnvironment = async (context: vscode.ExtensionContext): Promise<void> => {
	if (!vscode.workspace.isTrusted) {
		const selection = await vscode.window.showWarningMessage(
			'Environment check runs Python code. Trust this workspace to continue.',
			'Manage Workspace Trust',
			'Open README'
		);
		if (selection === 'Manage Workspace Trust') {
			await manageWorkspaceTrust();
			return;
		}
		if (selection === 'Open README') {
			const readmeUri = vscode.Uri.joinPath(context.extensionUri, 'README.md');
			await vscode.commands.executeCommand('vscode.open', readmeUri);
		}
		return;
	}

	const activeDocument = vscode.window.activeTextEditor?.document;
	const { interpreterPath: normalizedInterpreter } = resolveQ2lspConfig(activeDocument);
	if (normalizedInterpreter && !isAbsolutePath(normalizedInterpreter)) {
		await showValidationError({
			context,
			outputChannel,
			message: buildInterpreterPathNotAbsoluteMessage(),
			validation: { ok: false },
			interpreterPath: normalizedInterpreter,
		});
		return;
	}

	const pythonExtensionInterpreter = await resolveConfiguredPythonInterpreter(outputChannel);
	const candidates = buildInterpreterCandidates(
		normalizedInterpreter,
		pythonExtensionInterpreter,
		DEFAULT_PATH_CANDIDATES
	);
	if (candidates.length === 0) {
		await showValidationError({
			context,
			outputChannel,
			message: buildMissingInterpreterMessage(),
			validation: { ok: false },
			interpreterPath: '',
		});
		return;
	}

	const candidate = await selectInterpreterCandidate(candidates);
	if (!candidate) {
		return;
	}

	const validation = await validateInterpreter(execFileForValidation, candidate.path, VALIDATION_TIMEOUT_MS);
	appendValidationReport(candidate, validation);
	await showDiagnoseMessage({
		context,
		outputChannel,
		validation,
		interpreterPath: candidate.path,
	});
};
