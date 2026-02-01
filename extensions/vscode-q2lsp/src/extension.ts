import * as path from 'path';
import * as vscode from 'vscode';
import { execFile, type ExecFileException, type ExecFileOptionsWithStringEncoding } from 'child_process';
import { LanguageClient, type LanguageClientOptions, type ServerOptions } from 'vscode-languageclient/node';
import {
	DEFAULT_PATH_CANDIDATES,
	buildInterpreterCandidates,
	buildInterpreterPathNotAbsoluteMessage,
	buildInterpreterValidationMessage,
	buildInterpreterValidationSnippet,
	buildMissingInterpreterMessage,
	buildServerCommand,
	getUnsupportedPlatformMessage,
	isAbsolutePath,
	mergeEnv,
	parseInterpreterValidationStdout,
	shouldRestartOnConfigChange,
	type InterpreterCandidate,
} from './helpers';

type ValidationResult = {
	ok: boolean;
	stderr?: string;
	errorMessage?: string;
	missingModules?: string[];
};

const validationTimeoutMs = 2000;

let client: LanguageClient | undefined;
let outputChannel: vscode.OutputChannel | undefined;

type ExecFileRunner = (
	file: string,
	args: readonly string[],
	options: ExecFileOptionsWithStringEncoding,
	callback: (error: ExecFileException | null, stdout: string, stderr: string) => void
) => void;

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
		await client.stop();
	} finally {
		client = undefined;
	}
};

const startClient = async (context: vscode.ExtensionContext): Promise<void> => {
	const activeDocument = vscode.window.activeTextEditor?.document;
	const configScope = activeDocument?.uri;
	const configuration = configScope
		? vscode.workspace.getConfiguration('q2lsp', configScope)
		: vscode.workspace.getConfiguration('q2lsp');
	const configuredInterpreter = configuration.get<string>('interpreterPath');
	const normalizedInterpreter = configuredInterpreter?.trim() ? configuredInterpreter.trim() : undefined;
	const serverEnvOverrides = sanitizeServerEnvOverrides(configuration.get('serverEnv'));
	if (normalizedInterpreter && !isAbsolutePath(normalizedInterpreter)) {
		showError(buildInterpreterPathNotAbsoluteMessage(normalizedInterpreter));
		return;
	}
	const pythonExtensionInterpreter = await resolvePythonExtensionInterpreter();
	const candidates = buildInterpreterCandidates(
		normalizedInterpreter,
		pythonExtensionInterpreter,
		DEFAULT_PATH_CANDIDATES
	);

	if (candidates.length === 0) {
		showError(buildMissingInterpreterMessage());
		return;
	}

	const resolvedInterpreter = await resolveValidInterpreter(context, candidates);
	if (!resolvedInterpreter) {
		return;
	}

	const serverCommand = buildServerCommand(resolvedInterpreter.path);
	const cwd = resolveServerCwd(activeDocument);
	const serverOptions: ServerOptions = {
		command: serverCommand.command,
		args: serverCommand.args,
		options: {
			cwd,
			env: mergeEnv(process.env, serverEnvOverrides),
		},
	};

	const clientOptions: LanguageClientOptions = {
		documentSelector: [{ language: 'shellscript', scheme: 'file' }],
		outputChannel,
	};

	client = new LanguageClient('q2lsp', 'q2lsp', serverOptions, clientOptions);
	context.subscriptions.push(client);
	await client.start();
	outputChannel?.appendLine(`Started q2lsp using ${resolvedInterpreter.path}.`);
};

const resolveValidInterpreter = async (
	context: vscode.ExtensionContext,
	candidates: InterpreterCandidate[]
): Promise<InterpreterCandidate | undefined> => {
	let lastFailure: { candidate: InterpreterCandidate; validation: ValidationResult } | undefined;
	for (const candidate of candidates) {
		const validation = await validateInterpreter(execFileForValidation, candidate.path, validationTimeoutMs);
		if (validation.ok) {
			return candidate;
		}
		lastFailure = { candidate, validation };

		const message = buildInterpreterValidationMessage(
			candidate.path,
			validation.missingModules,
			validation.stderr ?? validation.errorMessage
		);
		outputChannel?.appendLine(message);
		if (candidate.source === 'config') {
			await showValidationError(context, message);
			return undefined;
		}
	}

	if (lastFailure) {
		const message = buildInterpreterValidationMessage(
			lastFailure.candidate.path,
			lastFailure.validation.missingModules,
			lastFailure.validation.stderr ?? lastFailure.validation.errorMessage
		);
		await showValidationError(context, message);
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

const execFileForValidation: ExecFileRunner = (file, args, options, callback) => {
	execFile(file, args, options, callback);
};

const validateInterpreter = (
	execFileFn: ExecFileRunner,
	interpreterPath: string,
	timeoutMs: number
): Promise<ValidationResult> => {
	return new Promise((resolve) => {
		const execOptions: ExecFileOptionsWithStringEncoding = {
			encoding: 'utf8',
			timeout: timeoutMs,
		};
		execFileFn(
			interpreterPath,
			['-c', buildInterpreterValidationSnippet()],
			execOptions,
			(error, stdout, stderr) => {
				if (error) {
					resolve({ ok: false, stderr, errorMessage: error.message });
					return;
				}
				const missingModules = parseInterpreterValidationStdout(stdout);
				if (missingModules === null) {
					const trimmed = stdout?.trim() ?? '';
					const snippet = trimmed.length > 200 ? `${trimmed.slice(0, 200)}...` : trimmed;
					resolve({
						ok: false,
						stderr,
						errorMessage: `Unexpected validation output (expected JSON). stdout: ${snippet}`,
					});
					return;
				}
				if (missingModules.length > 0) {
					resolve({ ok: false, stderr, missingModules });
					return;
				}
				if (!stdout?.trim()) {
					resolve({ ok: false, stderr, errorMessage: 'No validation output received.' });
					return;
				}
				resolve({ ok: true });
			}
		);
	});
};

const sanitizeServerEnvOverrides = (value: unknown): Record<string, string> => {
	if (!value || typeof value !== 'object') {
		return {};
	}

	const overrides: Record<string, string> = {};
	for (const [key, entry] of Object.entries(value as Record<string, unknown>)) {
		if (typeof entry === 'string') {
			overrides[key] = entry;
		}
	}

	return overrides;
};

const showError = (message: string): void => {
	outputChannel?.appendLine(message);
	vscode.window.showErrorMessage(message);
};

const showValidationError = async (context: vscode.ExtensionContext, message: string): Promise<void> => {
	const selection = await vscode.window.showErrorMessage(
		message,
		'Select Python Interpreter',
		'Open Settings',
		'Open README'
	);
	if (!selection) {
		return;
	}

	switch (selection) {
		case 'Select Python Interpreter':
			await selectPythonInterpreter();
			return;
		case 'Open Settings':
			await vscode.commands.executeCommand('workbench.action.openSettings', 'q2lsp.interpreterPath');
			return;
		case 'Open README': {
			const readmeUri = vscode.Uri.joinPath(context.extensionUri, 'README.md');
			const document = await vscode.workspace.openTextDocument(readmeUri);
			await vscode.window.showTextDocument(document, { preview: false });
			return;
		}
		default:
			return;
	}
};

const selectPythonInterpreter = async (): Promise<void> => {
	const pythonExtension = vscode.extensions.getExtension('ms-python.python');
	if (!pythonExtension) {
		vscode.window.showErrorMessage('Install the VS Code Python extension to select a Python interpreter.');
		return;
	}

	try {
		await vscode.commands.executeCommand('python.setInterpreter');
	} catch (error) {
		vscode.window.showErrorMessage(
			`Unable to open Python interpreter selection. Ensure the Python extension is installed. (${String(error)})`
		);
	}
};
