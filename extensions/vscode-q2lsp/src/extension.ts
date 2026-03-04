import * as path from 'path';
import * as vscode from 'vscode';
import { type LanguageClient } from 'vscode-languageclient/node';
import {
	DEFAULT_PATH_CANDIDATES,
	VALIDATION_TIMEOUT_MS,
	buildInterpreterCandidates,
	buildInterpreterPathNotAbsoluteMessage,
	buildInterpreterValidationMessage,
	buildMissingInterpreterMessage,
	formatOutputSnippet,
	getUnsupportedPlatformMessage,
	isAbsolutePath,
	shouldRestartOnConfigChange,
	type InterpreterCandidate,
} from './helpers';
import { resolveQ2lspConfig } from './config';
import { execFileForValidation, type ValidationResult, validateInterpreter } from './interpreter';
import { startQ2lspClient, stopQ2lspClient } from './client';
import {
	manageWorkspaceTrust,
	selectInterpreterCandidate,
	showDiagnoseMessage,
	showValidationError,
} from './diagnosis';

let client: LanguageClient | undefined;
let outputChannel: vscode.OutputChannel | undefined;

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
	if (normalizedInterpreter && !isAbsolutePath(normalizedInterpreter)) {
		const message = buildInterpreterPathNotAbsoluteMessage();
		outputChannel?.appendLine(message);
		vscode.window.showErrorMessage(message);
		return;
	}
	const pythonExtensionInterpreter = await resolvePythonExtensionInterpreter();
	const candidates = buildInterpreterCandidates(
		normalizedInterpreter,
		pythonExtensionInterpreter,
		DEFAULT_PATH_CANDIDATES
	);

	if (candidates.length === 0) {
		const message = buildMissingInterpreterMessage();
		outputChannel?.appendLine(message);
		vscode.window.showErrorMessage(message);
		return;
	}

	const resolvedInterpreter = await resolveValidInterpreter(context, candidates);
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

const resolveValidInterpreter = async (
	context: vscode.ExtensionContext,
	candidates: InterpreterCandidate[]
): Promise<InterpreterCandidate | undefined> => {
	let lastFailure: { candidate: InterpreterCandidate; validation: ValidationResult } | undefined;
	for (const candidate of candidates) {
		const validation = await validateInterpreter(execFileForValidation, candidate.path, VALIDATION_TIMEOUT_MS);
		if (validation.ok) {
			return candidate;
		}
		lastFailure = { candidate, validation };

		const message = buildInterpreterValidationMessage(candidate.path, validation.missingModules);
		outputChannel?.appendLine(message);
		const detail = validation.stderr ?? validation.errorMessage;
		if (detail?.trim()) {
			outputChannel?.appendLine(`Validation detail for ${candidate.path}: ${formatOutputSnippet(detail)}`);
		}
		if (candidate.source === 'config') {
			await showValidationError({
				context,
				outputChannel,
				message,
				validation,
				interpreterPath: candidate.path,
			});
			return undefined;
		}
	}

	if (lastFailure) {
		const message = buildInterpreterValidationMessage(
			lastFailure.candidate.path,
			lastFailure.validation.missingModules
		);
		await showValidationError({
			context,
			outputChannel,
			message,
			validation: lastFailure.validation,
			interpreterPath: lastFailure.candidate.path,
		});
	}

	return undefined;
};

const resolvePythonExtensionInterpreter = async (): Promise<string | undefined> => {
	const pythonExtension = vscode.extensions.getExtension('ms-python.python');
	if (!pythonExtension) {
		return undefined;
	}

	try {
		await pythonExtension.activate();
	} catch (error) {
		outputChannel?.appendLine(`Failed to activate Python extension: ${String(error)}`);
	}

	try {
		const interpreter = await vscode.commands.executeCommand<string>('python.interpreterPath');
		if (interpreter && interpreter.trim()) {
			return interpreter.trim();
		}
	} catch (error) {
		outputChannel?.appendLine(`Failed to query Python interpreter path: ${String(error)}`);
	}

	const pythonConfig = vscode.workspace.getConfiguration('python');
	const configured = pythonConfig.get<string>('defaultInterpreterPath');
	if (configured && configured.trim()) {
		return configured.trim();
	}

	return undefined;
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

	const pythonExtensionInterpreter = await resolvePythonExtensionInterpreter();
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
