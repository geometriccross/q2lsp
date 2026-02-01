import * as path from 'path';
import * as vscode from 'vscode';
import { execFile, type ExecFileException, type ExecFileOptionsWithStringEncoding } from 'child_process';
import { LanguageClient, type LanguageClientOptions, type ServerOptions } from 'vscode-languageclient/node';
import {
	DEFAULT_PATH_CANDIDATES,
	buildInterpreterCandidates,
	buildInterpreterPathNotAbsoluteMessage,
	buildInterpreterValidationMessage,
	buildMissingInterpreterMessage,
	buildServerCommand,
	getUnsupportedPlatformMessage,
	isAbsolutePath,
	mergeEnv,
	shouldRestartOnConfigChange,
	type InterpreterCandidate,
} from './helpers';

type ValidationResult = {
	ok: boolean;
	stderr?: string;
	errorMessage?: string;
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

	const resolvedInterpreter = await resolveValidInterpreter(candidates);
	if (!resolvedInterpreter) {
		if (!normalizedInterpreter) {
			showError(buildMissingInterpreterMessage());
		}
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
	candidates: InterpreterCandidate[]
): Promise<InterpreterCandidate | undefined> => {
	for (const candidate of candidates) {
		const validation = await validateInterpreter(execFileForValidation, candidate.path, validationTimeoutMs);
		if (validation.ok) {
			return candidate;
		}

		const message = buildInterpreterValidationMessage(
			candidate.path,
			validation.stderr ?? validation.errorMessage
		);
		outputChannel?.appendLine(message);
		if (candidate.source === 'config') {
			showError(message);
			return undefined;
		}
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

	const pythonConfig = vscode.workspace.getConfiguration('python');
	const configured = pythonConfig.get<string>('defaultInterpreterPath');
	if (configured && configured.trim()) {
		return configured.trim();
	}

	try {
		const interpreter = await vscode.commands.executeCommand<string>('python.interpreterPath');
		if (interpreter && interpreter.trim()) {
			return interpreter.trim();
		}
	} catch (error) {
		outputChannel?.appendLine(`Failed to query Python interpreter path: ${String(error)}`);
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
			['-c', 'import q2lsp'],
			execOptions,
			(error, _stdout, stderr) => {
				if (error) {
					resolve({ ok: false, stderr, errorMessage: error.message });
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
