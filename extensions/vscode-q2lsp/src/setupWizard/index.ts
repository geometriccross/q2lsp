import { execFile, type ExecFileOptionsWithStringEncoding } from 'child_process';
import * as vscode from 'vscode';
import { selectPythonInterpreter } from '../diagnosis';
import { VALIDATION_TIMEOUT_MS, buildInterpreterValidationSnippet, parseInterpreterValidationStdout } from '../helpers';
import { execFileForValidation, validateInterpreter } from '../interpreter';

import { buildSetupWizardHtml } from './view';
import {
	QIIME_QUICKSTART_URL,
	type QiimePlatform,
} from './qiimeConstants';
import { resolveQiimePlatform } from './qiimeMetadata';
import { refreshQiimeManifest } from './qiimeRemote';

export {
	SETUP_WIZARD_FLOW_STEPS,
	SETUP_WIZARD_MANAGERS,
	buildSetupWizardHtml,
} from './view';
export {
	QIIME_DISTRIBUTIONS,
	QIIME_PACKAGES_BASE_URL,
	QIIME_QUICKSTART_URL,
	QIIME_VERSIONS,
} from './qiimeConstants';
export {
	buildFallbackQiimeEnvironments,
	buildSyntheticQiimeEnvironment,
	mergeQiimeEnvironments,
	parseQiimeEnvironmentPath,
	resolveQiimePlatform,
} from './qiimeMetadata';
export { buildQiimeEnvironmentsFromTree } from './qiimeRemote';

type SetupWizardMessage = {
	command?: unknown;
	commandText?: unknown;
	interpreterPath?: unknown;
	manager?: unknown;
	environmentName?: unknown;
	environmentUrl?: unknown;
	condaSubdir?: unknown;
};

let currentPanel: vscode.WebviewPanel | undefined;

export const openSetupWizard = (params: {
	context: vscode.ExtensionContext;
	outputChannel?: vscode.OutputChannel;
	interpreterPath?: string;
}): void => {
	const { context, outputChannel, interpreterPath } = params;
	const platform = resolveQiimePlatform(process.platform, process.arch);
	if (currentPanel) {
		currentPanel.reveal(vscode.ViewColumn.One);
		currentPanel.webview.html = buildSetupWizardHtml({
			nonce: createNonce(),
			interpreterPath,
			platform,
			environments: [],
		});
		void refreshQiimeManifest(currentPanel.webview);
		return;
	}

	const panel = vscode.window.createWebviewPanel(
		'q2lspSetupWizard',
		'q2lsp Setup Wizard',
		vscode.ViewColumn.One,
		{
			enableScripts: true,
		}
	);
	currentPanel = panel;
	panel.webview.html = buildSetupWizardHtml({
		nonce: createNonce(),
		interpreterPath,
		platform,
		environments: [],
	});
	void refreshQiimeManifest(panel.webview);

	const messageDisposable = panel.webview.onDidReceiveMessage(
		async (message: SetupWizardMessage) => {
			await handleSetupWizardMessage({
				message,
				outputChannel,
				webview: panel.webview,
			});
		}
	);
	panel.onDidDispose(() => {
		messageDisposable.dispose();
		currentPanel = undefined;
	});
	context.subscriptions.push(panel);
};


const handleSetupWizardMessage = async (params: {
	message: SetupWizardMessage;
	outputChannel?: vscode.OutputChannel;
	webview: vscode.Webview;
}): Promise<void> => {
	const command = toNonEmptyString(params.message.command);
	if (!command) {
		return;
	}

	switch (command) {
		case 'installManager':
			await confirmAndRunInTerminal(command, params.message.commandText);
			const managerCommand = toNonEmptyString(params.message.commandText);
			await postWizardStatus(params.webview, {
				message: managerCommand?.startsWith('Open ')
					? 'Opened setup documentation. When installation finishes, choose "I installed it, check again".'
					: 'Install command sent to terminal. When it finishes, choose "I installed it, check again".',
			});
			return;
		case 'createQiimeEnvironment':
			await createQiimeEnvironmentForWizard(params.webview, params.message);
			return;
		case 'installQ2lsp': {
			const manager = toNonEmptyString(params.message.manager);
			const interpreterResult = await resolveWizardInterpreter(params.message);
			if (!interpreterResult.ok) {
				await postWizardStatus(params.webview, {
					q2lspStatus: 'missing',
					message: interpreterResult.message,
				});
				return;
			}
			const installResult = await installQ2lspForWizard(manager, interpreterResult.interpreterPath);
			if (!installResult.ok) {
				await postWizardStatus(params.webview, {
					interpreterPath: interpreterResult.interpreterPath,
					q2lspStatus: 'missing',
					message: installResult.message,
				});
				return;
			}
			const validation = await validateInterpreter(
				execFileForValidation,
				interpreterResult.interpreterPath,
				VALIDATION_TIMEOUT_MS
			);
			await postWizardStatus(params.webview, {
				interpreterPath: interpreterResult.interpreterPath,
				q2lspStatus: validation.ok ? 'ready' : 'missing',
				message: validation.ok
					? 'q2lsp installed and validated.'
					: validation.missingModules?.length
						? `q2lsp install finished, but validation is still missing: ${validation.missingModules.join(', ')}.`
						: validation.errorMessage ?? 'q2lsp install finished, but validation failed.',
			});
			return;
		}
		case 'selectPythonInterpreter':
			await selectPythonInterpreter();
			return;
		case 'checkManager':
			await checkSelectedManager(params.webview, params.message.manager);
			return;
		case 'validateEnvironment':
			await validateQiimeEnvironment(params.webview, params.message);
			return;
		case 'validateQ2lsp':
			await validateQ2lsp(params.webview, params.message);
			return;
		case 'saveInterpreterPath':
			await saveInterpreterPath(params.webview, params.message);
			return;
		case 'restartServer':
			await vscode.commands.executeCommand('q2lsp.restartServer');
			await postWizardStatus(params.webview, {
				message: 'Restarted q2lsp server.',
			});
			return;
		default:
			return;
	}
};

const checkSelectedManager = async (webview: vscode.Webview, managerValue: unknown): Promise<void> => {
	const manager = toNonEmptyString(managerValue);
	if (manager === 'manual') {
		await postWizardStatus(webview, { managerStatus: 'ready', message: 'Manual setup selected.' });
		return;
	}

	const executable = manager === 'pixi' ? 'pixi' : 'conda';
	const result = await runExecutable(executable, ['--version']);
	if (result.ok) {
		await postWizardStatus(webview, {
			managerStatus: 'ready',
			message: `${executable} is available: ${formatStatusDetail(result.stdout)}`,
		});
		return;
	}

	await postWizardStatus(webview, {
		managerStatus: 'missing',
		message: `${executable} was not found. Install it, then check again.`,
	});
};

const createQiimeEnvironmentForWizard = async (
	webview: vscode.Webview,
	message: SetupWizardMessage
): Promise<void> => {
	const manager = toNonEmptyString(message.manager);
	const environmentName = toNonEmptyString(message.environmentName);
	const environmentUrl = toNonEmptyString(message.environmentUrl);
	if (manager === 'manual') {
		await vscode.env.openExternal(vscode.Uri.parse(QIIME_QUICKSTART_URL));
		await postWizardStatus(webview, {
			message: 'Opened QIIME 2 Quickstart. Return to validate your selected interpreter after setup.',
		});
		return;
	}
	if (!environmentName || !environmentUrl) {
		await postWizardStatus(webview, {
			qiimeStatus: 'missing',
			message: 'Could not resolve QIIME 2 environment metadata.',
		});
		return;
	}

	const selection = await vscode.window.showWarningMessage(
		`Create QIIME 2 environment ${environmentName} now? This can take a long time.`,
		{ modal: true },
		'Create Environment'
	);
	if (selection !== 'Create Environment') {
		await postWizardStatus(webview, {
			message: 'QIIME environment creation was cancelled.',
		});
		return;
	}

	const result = await vscode.window.withProgress(
		{
			location: vscode.ProgressLocation.Notification,
			title: `Creating ${environmentName}`,
			cancellable: false,
		},
		async () => {
			if (manager === 'pixi') {
				return createPixiQiimeEnvironment(environmentUrl);
			}
			return createCondaQiimeEnvironment(environmentName, environmentUrl, toNonEmptyString(message.condaSubdir));
		}
	);
	if (!result.ok) {
		await postWizardStatus(webview, {
			qiimeStatus: 'missing',
			message: result.message,
		});
		return;
	}

	const interpreterResult = await resolveWizardInterpreter(message);
	if (!interpreterResult.ok) {
		await postWizardStatus(webview, {
			qiimeStatus: 'missing',
			message: interpreterResult.message,
		});
		return;
	}

	const validation = await runPythonValidation(interpreterResult.interpreterPath, ['q2cli', 'qiime2']);
	await postWizardStatus(webview, {
		interpreterPath: interpreterResult.interpreterPath,
		qiimeStatus: validation.ok ? 'ready' : 'missing',
		message: validation.ok ? 'QIIME 2 environment created and validated.' : validation.message,
	});
};

const createCondaQiimeEnvironment = async (
	environmentName: string,
	environmentUrl: string,
	condaSubdir: string | undefined
): Promise<{ ok: true } | { ok: false; message: string }> => {
	const result = await runExecutable(
		'conda',
		['env', 'create', '--name', environmentName, '--file', environmentUrl],
		undefined,
		3600000,
		condaSubdir ? { CONDA_SUBDIR: condaSubdir } : undefined
	);
	return result.ok ? { ok: true } : { ok: false, message: result.message };
};

const createPixiQiimeEnvironment = async (
	environmentUrl: string
): Promise<{ ok: true } | { ok: false; message: string }> => {
	const pixiCwd = resolvePixiProjectCwd();
	if (!pixiCwd) {
		return { ok: false, message: 'Open a workspace before creating a Pixi QIIME 2 environment.' };
	}

	const initResult = await runExecutable(
		'pixi',
		['init'],
		pixiCwd,
		600000
	);
	if (!initResult.ok && !initResult.message.includes('already')) {
		return { ok: false, message: initResult.message };
	}

	const importResult = await runExecutable(
		'pixi',
		['import', environmentUrl],
		pixiCwd,
		3600000
	);
	if (!importResult.ok) {
		return { ok: false, message: importResult.message };
	}

	const installResult = await runExecutable('pixi', ['install'], pixiCwd, 3600000);
	return installResult.ok ? { ok: true } : { ok: false, message: installResult.message };
};

const validateQiimeEnvironment = async (webview: vscode.Webview, message: SetupWizardMessage): Promise<void> => {
	const interpreterResult = await resolveWizardInterpreter(message);
	if (!interpreterResult.ok) {
		await postWizardStatus(webview, {
			qiimeStatus: 'missing',
			q2lspStatus: 'unknown',
			message: interpreterResult.message,
		});
		return;
	}
	const interpreterPath = interpreterResult.interpreterPath;

	const result = await runPythonValidation(interpreterPath, ['q2cli', 'qiime2']);
	if (result.ok) {
		await postWizardStatus(webview, {
			interpreterPath,
			qiimeStatus: 'ready',
			message: 'QIIME 2 validation passed.',
		});
		return;
	}

	await postWizardStatus(webview, {
		interpreterPath,
		qiimeStatus: 'missing',
		message: result.message,
	});
};

const validateQ2lsp = async (webview: vscode.Webview, message: SetupWizardMessage): Promise<void> => {
	const interpreterResult = await resolveWizardInterpreter(message);
	if (!interpreterResult.ok) {
		await postWizardStatus(webview, {
			q2lspStatus: 'missing',
			message: interpreterResult.message,
		});
		return;
	}
	const interpreterPath = interpreterResult.interpreterPath;

	const result = await validateInterpreter(execFileForValidation, interpreterPath, VALIDATION_TIMEOUT_MS);
	if (result.ok) {
		await postWizardStatus(webview, {
			interpreterPath,
			qiimeStatus: 'ready',
			q2lspStatus: 'ready',
			message: 'q2lsp validation passed.',
		});
		return;
	}

	await postWizardStatus(webview, {
		interpreterPath,
		q2lspStatus: 'missing',
		message: result.missingModules?.length
			? `Missing modules: ${result.missingModules.join(', ')}.`
			: result.errorMessage ?? 'q2lsp validation failed.',
	});
};

const saveInterpreterPath = async (webview: vscode.Webview, message: SetupWizardMessage): Promise<void> => {
	const interpreterResult = await resolveWizardInterpreter(message);
	if (!interpreterResult.ok) {
		await postWizardStatus(webview, {
			message: interpreterResult.message,
		});
		return;
	}
	const interpreterPath = interpreterResult.interpreterPath;

	const scope = await vscode.window.showQuickPick(
		[
			{
				label: 'Workspace',
				description: 'Recommended for project-specific QIIME 2 environments',
				target: vscode.ConfigurationTarget.Workspace,
			},
			{
				label: 'User',
				description: 'Use this interpreter for all workspaces',
				target: vscode.ConfigurationTarget.Global,
			},
		],
		{
			placeHolder: 'Where should q2lsp.interpreterPath be saved?',
		}
	);
	if (!scope) {
		await postWizardStatus(webview, {
			message: 'Saving q2lsp.interpreterPath was cancelled.',
		});
		return;
	}

	await vscode.workspace.getConfiguration('q2lsp').update(
		'interpreterPath',
		interpreterPath,
		scope.target
	);
	await postWizardStatus(webview, {
		interpreterPath,
		savedInterpreterPath: true,
		message: `Saved q2lsp.interpreterPath to ${scope.label.toLowerCase()} settings.`,
	});
};

const resolveWizardInterpreter = async (
	message: SetupWizardMessage
): Promise<{ ok: true; interpreterPath: string } | { ok: false; message: string }> => {
	const manager = toNonEmptyString(message.manager);
	const environmentName = toNonEmptyString(message.environmentName);
	const explicitInterpreterPath = toNonEmptyString(message.interpreterPath);

	if (manager === 'conda' && environmentName) {
		const result = await runExecutable('conda', [
			'run',
			'-n',
			environmentName,
			'python',
			'-c',
			'import sys; print(sys.executable)',
		]);
		if (result.ok) {
			return { ok: true, interpreterPath: result.stdout.trim() };
		}
		return { ok: false, message: `Could not resolve Conda environment ${environmentName}: ${result.message}` };
	}

	if (manager === 'pixi') {
		const result = await runExecutable(
			'pixi',
			['run', 'python', '-c', 'import sys; print(sys.executable)'],
			resolvePixiProjectCwd()
		);
		if (result.ok) {
			return { ok: true, interpreterPath: result.stdout.trim() };
		}
		return { ok: false, message: `Could not resolve Pixi Python interpreter: ${result.message}` };
	}

	if (explicitInterpreterPath) {
		return { ok: true, interpreterPath: explicitInterpreterPath };
	}

	return { ok: false, message: 'Select or create a QIIME 2 Python interpreter before continuing.' };
};

const installQ2lspForWizard = async (
	manager: string | undefined,
	interpreterPath: string
): Promise<{ ok: true } | { ok: false; message: string }> => {
	const selection = await vscode.window.showWarningMessage(
		'Install q2lsp into the selected QIIME 2 environment now?',
		{ modal: true },
		'Install q2lsp'
	);
	if (selection !== 'Install q2lsp') {
		return { ok: false, message: 'q2lsp install was cancelled.' };
	}

	return vscode.window.withProgress(
		{
			location: vscode.ProgressLocation.Notification,
			title: 'Installing q2lsp',
			cancellable: false,
		},
		async () => {
			if (manager === 'pixi') {
				const result = await runExecutable(
					'pixi',
					['run', 'python', '-m', 'pip', 'install', '-U', 'q2lsp'],
					resolvePixiProjectCwd(),
					600000
				);
				return result.ok ? { ok: true } : { ok: false, message: result.message };
			}

			const result = await runExecutable(
				interpreterPath,
				['-m', 'pip', 'install', '-U', 'q2lsp'],
				undefined,
				600000
			);
			return result.ok ? { ok: true } : { ok: false, message: result.message };
		}
	);
};

const postWizardStatus = async (
	webview: vscode.Webview,
	patch: Record<string, string | boolean>
): Promise<void> => {
	await webview.postMessage({
		type: 'wizardStatus',
		patch,
	});
};

const runPythonValidation = async (
	interpreterPath: string,
	modules: readonly string[]
): Promise<{ ok: true } | { ok: false; message: string }> => {
	const result = await runExecutable(interpreterPath, ['-c', buildInterpreterValidationSnippet(modules)]);
	if (!result.ok) {
		return { ok: false, message: result.message };
	}

	const details = parseInterpreterValidationStdout(result.stdout);
	if (!details) {
		return { ok: false, message: 'Unexpected Python validation output.' };
	}
	if (details.missing.length > 0) {
		return { ok: false, message: `Missing modules: ${details.missing.join(', ')}.` };
	}
	return { ok: true };
};

const runExecutable = async (
	file: string,
	args: readonly string[],
	cwd?: string,
	timeoutMs: number = VALIDATION_TIMEOUT_MS,
	envOverrides?: NodeJS.ProcessEnv
): Promise<{ ok: true; stdout: string } | { ok: false; message: string }> => {
	return new Promise((resolve) => {
		const execOptions: ExecFileOptionsWithStringEncoding = {
			encoding: 'utf8',
			timeout: timeoutMs,
			env: envOverrides ? { ...process.env, ...envOverrides } : process.env,
			...(cwd ? { cwd } : {}),
		};
		execFile(file, args, execOptions, (error, stdout, stderr) => {
			if (error) {
				resolve({
					ok: false,
					message: formatStatusDetail(stderr) || error.message,
				});
				return;
			}
			resolve({ ok: true, stdout });
		});
	});
};

const resolvePixiProjectCwd = (): string | undefined => {
	const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
	if (!workspaceFolder || workspaceFolder.uri.scheme !== 'file') {
		return undefined;
	}
	return workspaceFolder.uri.fsPath;
};

const formatStatusDetail = (value: string | undefined): string => {
	const trimmed = value?.trim();
	if (!trimmed) {
		return '';
	}
	return trimmed.length > 160 ? `${trimmed.slice(0, 160)}...` : trimmed;
};

const confirmAndRunInTerminal = async (action: string, commandText: unknown): Promise<void> => {
	const command = toNonEmptyString(commandText);
	if (!command || command.startsWith('Open ')) {
		if (command?.includes('QIIME 2 Quickstart')) {
			await vscode.env.openExternal(vscode.Uri.parse(QIIME_QUICKSTART_URL));
			return;
		}
		vscode.window.showInformationMessage(command ?? 'Follow the manual setup instructions, then return to the wizard.');
		return;
	}

	const selection = await vscode.window.showWarningMessage(
		`Run ${action} command in a VS Code terminal?`,
		{ modal: true },
		'Run in Terminal'
	);
	if (selection !== 'Run in Terminal') {
		return;
	}

	const terminal = vscode.window.createTerminal({ name: 'q2lsp Setup Wizard' });
	terminal.show(true);
	terminal.sendText(command);
};

const toNonEmptyString = (value: unknown): string | undefined => {
	return typeof value === 'string' && value.trim() ? value.trim() : undefined;
};

const createNonce = (): string => {
	const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
	let text = '';
	for (let index = 0; index < 32; index += 1) {
		text += possible.charAt(Math.floor(Math.random() * possible.length));
	}
	return text;
};
