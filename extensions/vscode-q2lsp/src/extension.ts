import * as path from 'path';
import * as vscode from 'vscode';
import { execFile, type ExecFileException, type ExecFileOptionsWithStringEncoding } from 'child_process';
import { LanguageClient, type LanguageClientOptions, type ServerOptions } from 'vscode-languageclient/node';
import {
	DEFAULT_PATH_CANDIDATES,
	QIIME2_QUICKSTART_URL,
	Q2CLI_MISSING_QIIME_HINT,
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
	type InterpreterValidationDetails,
	type InterpreterCandidate,
} from './helpers';

type ValidationResult = {
	ok: boolean;
	stdout?: string;
	stderr?: string;
	errorMessage?: string;
	missingModules?: string[];
	details?: InterpreterValidationDetails;
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
		const detail = validation.stderr ?? validation.errorMessage;
		if (detail?.trim()) {
			outputChannel?.appendLine(`Validation detail for ${candidate.path}: ${formatOutputSnippet(detail)}`);
		}
		if (candidate.source === 'config') {
			await showValidationError(context, message, validation, candidate.path);
			return undefined;
		}
	}

	if (lastFailure) {
		const message = buildInterpreterValidationMessage(
			lastFailure.candidate.path,
			lastFailure.validation.missingModules,
			lastFailure.validation.stderr ?? lastFailure.validation.errorMessage
		);
		await showValidationError(context, message, lastFailure.validation, lastFailure.candidate.path);
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
					resolve({ ok: false, stdout, stderr, errorMessage: error.message });
					return;
				}
				const details = parseInterpreterValidationStdout(stdout);
				if (details === null) {
					const trimmed = stdout?.trim() ?? '';
					const snippet = trimmed.length > 200 ? `${trimmed.slice(0, 200)}...` : trimmed;
					resolve({
						ok: false,
						stdout,
						stderr,
						errorMessage: `Unexpected validation output (expected JSON). stdout: ${snippet}`,
					});
					return;
				}
				if (details.missing.length > 0) {
					resolve({ ok: false, stdout, stderr, missingModules: details.missing, details });
					return;
				}
				resolve({ ok: true, stdout, stderr, details });
			}
		);
	});
};

const formatOutputSnippet = (value: string | undefined): string => {
	const trimmed = value?.trim();
	if (!trimmed) {
		return '<empty>';
	}
	if (trimmed.length > 400) {
		return `${trimmed.slice(0, 400)}...`;
	}
	return trimmed;
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

const selectInterpreterCandidate = async (
	candidates: InterpreterCandidate[]
): Promise<InterpreterCandidate | undefined> => {
	if (candidates.length === 1) {
		return candidates[0];
	}

	const items = candidates.map((candidate) => ({
		label: candidate.path,
		description:
			candidate.source === 'config'
				? 'Configured'
				: candidate.source === 'pythonExtension'
					? 'Python extension'
					: 'PATH',
		candidate,
	}));
	const selection = await vscode.window.showQuickPick(items, {
		placeHolder: 'Select a Python interpreter to diagnose q2lsp',
	});
	return selection?.candidate;
};

const buildRepairActions = (missingModules: readonly string[] | undefined): string[] => {
	const hasMissingQ2cli = missingModules?.includes('q2cli') ?? false;
	const actions = [
		'Select Python Interpreter',
		'Open Settings',
		hasMissingQ2cli ? 'Open QIIME 2 Quickstart' : 'Open README',
		'Show q2lsp Log',
	];
	if (missingModules?.includes('q2lsp')) {
		return ['Install q2lsp', ...actions];
	}
	return actions;
};

const showDiagnoseMessage = async (
	context: vscode.ExtensionContext,
	message: string,
	validation: ValidationResult | undefined,
	interpreterPath: string | undefined,
	isSuccess: boolean
): Promise<void> => {
	const actions = buildRepairActions(validation?.missingModules);
	const selection = isSuccess
		? await vscode.window.showInformationMessage(message, ...actions)
		: await vscode.window.showErrorMessage(message, ...actions);
	if (!selection) {
		return;
	}
	await handleRepairSelection(context, selection, interpreterPath);
};

const handleRepairSelection = async (
	context: vscode.ExtensionContext,
	selection: string,
	interpreterPath: string | undefined
): Promise<void> => {
		switch (selection) {
			case 'Select Python Interpreter':
				await selectPythonInterpreter();
				return;
			case 'Open Settings':
				await vscode.commands.executeCommand('workbench.action.openSettings', 'q2lsp.interpreterPath');
				return;
			case 'Open QIIME 2 Quickstart':
				await vscode.env.openExternal(vscode.Uri.parse(QIIME2_QUICKSTART_URL));
				return;
			case 'Open README':
				await openReadme(context);
				return;
		case 'Show q2lsp Log':
			outputChannel?.show(true);
			return;
		case 'Install q2lsp':
			if (interpreterPath) {
				await confirmAndInstallQ2lsp(interpreterPath);
			}
			return;
		default:
			return;
	}
};

const confirmAndInstallQ2lsp = async (interpreterPath: string): Promise<void> => {
	const command = `"${interpreterPath}" -m pip install -U q2lsp`;
	const selection = await vscode.window.showWarningMessage(
		'Install q2lsp in this interpreter now?',
		{ modal: true },
		'Install q2lsp'
	);
	if (selection !== 'Install q2lsp') {
		return;
	}

	const hasPip = await checkPipAvailable(interpreterPath);
	if (!hasPip) {
		vscode.window.showErrorMessage(
			'pip is not available for this interpreter. Install pip, then retry.'
		);
		return;
	}

	const terminal = vscode.window.createTerminal({ name: 'q2lsp Install' });
	terminal.show(true);
	terminal.sendText(command);
};

const checkPipAvailable = async (interpreterPath: string): Promise<boolean> => {
	return new Promise((resolve) => {
		const execOptions: ExecFileOptionsWithStringEncoding = {
			encoding: 'utf8',
			timeout: validationTimeoutMs,
		};
		execFileForValidation(interpreterPath, ['-m', 'pip', '--version'], execOptions, (error, stdout, stderr) => {
			if (error || !stdout?.trim()) {
				outputChannel?.appendLine(
					`pip check failed for ${interpreterPath}. stderr: ${formatOutputSnippet(stderr)}`
				);
				resolve(false);
				return;
			}
			resolve(true);
		});
	});
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
			await openReadme(context);
		}
		return;
	}

	const activeDocument = vscode.window.activeTextEditor?.document;
	const configScope = activeDocument?.uri;
	const configuration = configScope
		? vscode.workspace.getConfiguration('q2lsp', configScope)
		: vscode.workspace.getConfiguration('q2lsp');
	const configuredInterpreter = configuration.get<string>('interpreterPath');
	const normalizedInterpreter = configuredInterpreter?.trim() ? configuredInterpreter.trim() : undefined;
	if (normalizedInterpreter && !isAbsolutePath(normalizedInterpreter)) {
		await showDiagnoseMessage(
			context,
			buildInterpreterPathNotAbsoluteMessage(normalizedInterpreter),
			undefined,
			normalizedInterpreter,
			false
		);
		return;
	}

	const pythonExtensionInterpreter = await resolvePythonExtensionInterpreter();
	const candidates = buildInterpreterCandidates(
		normalizedInterpreter,
		pythonExtensionInterpreter,
		DEFAULT_PATH_CANDIDATES
	);
	if (candidates.length === 0) {
		await showDiagnoseMessage(context, buildMissingInterpreterMessage(), undefined, undefined, false);
		return;
	}

	const candidate = await selectInterpreterCandidate(candidates);
	if (!candidate) {
		return;
	}

	const validation = await validateInterpreter(execFileForValidation, candidate.path, validationTimeoutMs);
	appendValidationReport(candidate, validation);

	if (validation.ok && validation.details) {
		await showDiagnoseMessage(
			context,
			'Environment is ready. q2lsp checks passed.',
			validation,
			candidate.path,
			true
		);
		return;
	}

	if (validation.missingModules?.length) {
		const q2cliHint = validation.missingModules.includes('q2cli')
			? Q2CLI_MISSING_QIIME_HINT
			: '';
		await showDiagnoseMessage(
			context,
			`Required modules missing: ${validation.missingModules.join(', ')}.${q2cliHint}`,
			validation,
			candidate.path,
			false
		);
		return;
	}

	await showDiagnoseMessage(
		context,
		"q2lsp couldn't validate this interpreter. See q2lsp log for details.",
		validation,
		candidate.path,
		false
	);
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

const showValidationError = async (
	context: vscode.ExtensionContext,
	message: string,
	validation: ValidationResult,
	interpreterPath: string
): Promise<void> => {
	const actions = buildRepairActions(validation.missingModules);
	const selection = await vscode.window.showErrorMessage(message, ...actions);
	if (!selection) {
		return;
	}
	await handleRepairSelection(context, selection, interpreterPath);
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

const manageWorkspaceTrust = async (): Promise<void> => {
	const commands = ['workbench.action.manageTrust', 'workbench.trust.manage', 'workbench.action.openWorkspaceTrustEditor'];
	for (const command of commands) {
		try {
			await vscode.commands.executeCommand(command);
			return;
		} catch {
			// ignore
		}
	}
};

const openReadme = async (context: vscode.ExtensionContext): Promise<void> => {
	const readmeUri = vscode.Uri.joinPath(context.extensionUri, 'README.md');
	const document = await vscode.workspace.openTextDocument(readmeUri);
	await vscode.window.showTextDocument(document, { preview: false });
};
