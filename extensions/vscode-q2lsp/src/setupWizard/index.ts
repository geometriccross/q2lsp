import * as vscode from 'vscode';
import { manageWorkspaceTrust } from '../diagnosis';
import { resolveConfiguredPythonInterpreter } from '../interpreter_resolver';
import { createQiimeEnvironment, createSetupTools, type SetupTools } from './environment';
import { QIIME_QUICKSTART_URL } from './qiimeConstants';
import { resolveQiimePlatform } from './qiimeMetadata';

export const registerSetupWizard = (
	context: vscode.ExtensionContext,
	output: vscode.OutputChannel,
	tools: SetupTools = createSetupTools(output),
): void => {
	const category = `${context.extension.id}#q2lsp.setup`;
	let interpreterPath: string | undefined;
	let busy = false;

	const openStep = async (step: string = 'environment'): Promise<void> => {
		await vscode.commands.executeCommand('workbench.action.openWalkthrough', { category, step });
	};
	// VS Code persists walkthrough progress. Update it explicitly so a click or
	// a cancelled operation cannot count as validation of the selected target.
	const progress = async (environment = false, server = false, saved = false): Promise<void> => {
		for (const [step, complete] of [['environment', environment], ['server', server], ['finish', saved]] as const) {
			for (let attempt = 0; ; attempt++) {
				try {
					await vscode.commands.executeCommand(
						complete ? 'welcome.markStepComplete' : 'welcome.markStepIncomplete', `${category}#${step}`,
					);
					break;
				} catch (error) {
					// Cold-start walkthrough registration can take up to five seconds in VS Code.
					if (attempt >= 12 || !String(error).includes('does not exist in registry')) {
						throw error;
					}
					await new Promise((resolve) => setTimeout(resolve, 500));
				}
			}
		}
	};
	const checkEnvironment = async (candidate: string): Promise<boolean> => {
		await progress();
		const result = await vscode.window.withProgress({
			location: vscode.ProgressLocation.Notification,
			title: 'Checking QIIME 2 environment',
		}, () => tools.check(candidate));
		interpreterPath = result.executable;
		const missingQiime = result.missing.filter((module) => module !== 'q2lsp');
		const serverReady = result.missing.length === 0;
		await progress(missingQiime.length === 0, serverReady);
		if (missingQiime.length > 0) {
			throw new Error(`Missing ${missingQiime.join(', ')} in ${interpreterPath}. Choose another environment or create one.`);
		}
		return serverReady;
	};

	const createEnvironment = async (): Promise<{ interpreterPath: string; activationHint: string } | undefined> => {
		const manager = await vscode.window.showQuickPick([
			{ label: 'Conda / Miniconda', description: 'Recommended', id: 'conda' as const },
			{ label: 'Pixi', description: 'Advanced: project-local environment', id: 'pixi' as const },
			{ label: 'Manual setup', description: 'Follow the QIIME 2 Quickstart', id: 'manual' as const },
		], { title: 'Create a QIIME 2 environment', placeHolder: 'Choose an environment manager' });
		if (!manager) {
			return undefined;
		}
		if (manager.id === 'manual') {
			await vscode.env.openExternal(vscode.Uri.parse(QIIME_QUICKSTART_URL));
			return undefined;
		}
		try {
			await tools.run(manager.id, ['--version']);
		} catch {
			const action = await vscode.window.showWarningMessage(
				`${manager.label} was not found. Install it, then run this step again.`, 'Open Installation Guide',
			);
			if (action) {
				await vscode.env.openExternal(vscode.Uri.parse(manager.id === 'conda'
					? 'https://www.anaconda.com/docs/getting-started/miniconda/install'
					: 'https://pixi.sh/latest/installation/'));
			}
			return undefined;
		}

		const platform = resolveQiimePlatform(process.platform, process.arch);
		const environments = await vscode.window.withProgress({
			location: vscode.ProgressLocation.Notification,
			title: 'Loading QIIME 2 environments',
		}, tools.environments);
		const targets = environments.filter((environment) => environment.platform === platform.id);
		if (targets.length === 0) {
			throw new Error('Could not load QIIME 2 environments for this platform. Retry this step or use the QIIME 2 Quickstart.');
		}
		const target = await vscode.window.showQuickPick(targets.map((environment) => ({
			label: environment.distribution,
			description: environment.version,
			detail: environment.fileName,
			environment,
		})), {
			title: `QIIME 2 environment — ${platform.label}`,
			placeHolder: 'Choose a distribution and version (newest first)',
			matchOnDescription: true,
		});
		if (!target) {
			return undefined;
		}
		let cwd: string | undefined;
		if (manager.id === 'pixi') {
			const folders = await vscode.window.showOpenDialog({
				title: 'Choose a Pixi project or an empty folder',
				canSelectFiles: false, canSelectFolders: true, canSelectMany: false,
				defaultUri: vscode.workspace.workspaceFolders?.[0]?.uri,
			});
			if (!folders?.[0] || folders[0].scheme !== 'file') {
				return undefined;
			}
			cwd = folders[0].fsPath;
		}
		const environmentName = manager.id === 'pixi' ? 'default' : target.environment.environmentName;
		const selection = await vscode.window.showWarningMessage(
			`Create ${target.environment.distribution} ${target.environment.version} with ${manager.label}?`,
			{
				modal: true,
				detail: `Environment: ${environmentName}\nPlatform: ${platform.label}\n${cwd ? `Pixi project files will be created or updated in ${cwd}. This will replace the default environment with one using only the "${target.environment.environmentName}" feature.\n` : ''}${target.environment.url}\n\nThis downloads packages and can take a long time.`,
			},
			'Create Environment',
		);
		if (!selection) {
			return undefined;
		}
		interpreterPath = undefined;
		await progress();
		const createdInterpreter = await vscode.window.withProgress({
			location: vscode.ProgressLocation.Notification,
			title: `Creating ${environmentName}`,
			cancellable: false,
		}, () => createQiimeEnvironment(tools.run, manager.id, target.environment, platform, cwd));
		return {
			interpreterPath: createdInterpreter,
			activationHint: manager.id === 'pixi'
				? `To use QIIME 2 in a terminal, run "pixi shell" in ${cwd}. QIIME 2 is included in the default environment.`
				: `To use QIIME 2 in a terminal, run "conda activate ${target.environment.environmentName}".`,
		};
	};

	const chooseEnvironment = async (): Promise<void> => {
		const configured = vscode.workspace.getConfiguration('q2lsp').get<string>('interpreterPath')?.trim();
		const python = await resolveConfiguredPythonInterpreter(output);
		const paths = [...new Set([configured, python, 'python3', 'python'].filter((value): value is string => !!value))];
		const items: Array<vscode.QuickPickItem & { path?: string; action?: 'browse' | 'create' }> = paths.map((path) => ({
			label: path,
			description: path === configured ? 'Configured for q2lsp' : path === python ? 'Python extension' : 'From PATH',
			path,
		}));
		items.push(
			{ label: 'Browse for Python…', action: 'browse' },
			{ label: 'Create a QIIME 2 environment…', action: 'create' },
		);
		const selection = await vscode.window.showQuickPick(items, {
			title: 'Set up your QIIME 2 environment',
			placeHolder: 'Select an existing Python interpreter or create an environment',
		});
		if (!selection) {
			return;
		}
		let candidate = selection.path;
		let activationHint: string | undefined;
		if (selection.action === 'browse') {
			const files = await vscode.window.showOpenDialog({
				title: 'Select the Python executable in your QIIME 2 environment',
				canSelectFiles: true, canSelectFolders: false, canSelectMany: false,
				openLabel: 'Select Python',
			});
			candidate = files?.[0]?.scheme === 'file' ? files[0].fsPath : undefined;
		} else if (selection.action === 'create') {
			const created = await createEnvironment();
			candidate = created?.interpreterPath;
			activationHint = created?.activationHint;
		}
		if (!candidate) {
			return;
		}
		interpreterPath = candidate;
		const ready = await checkEnvironment(candidate);
		if (activationHint) {
			output.appendLine(activationHint);
			void vscode.window.showInformationMessage(activationHint, 'Show Log').then((action) => {
				if (action) {
					output.show(true);
				}
			});
		}
		await openStep(ready ? 'finish' : 'server');
	};

	const prepareServer = async (): Promise<void> => {
		if (!interpreterPath) {
			await chooseEnvironment();
		}
		if (!interpreterPath) {
			return;
		}
		if (!await checkEnvironment(interpreterPath)) {
			const selection = await vscode.window.showWarningMessage('Install q2lsp in this environment?', {
				modal: true, detail: `${interpreterPath}\n\nOnly this Python environment will be changed.`,
			}, 'Install q2lsp');
			if (!selection) {
				return;
			}
			await vscode.window.withProgress({
				location: vscode.ProgressLocation.Notification, title: 'Installing q2lsp', cancellable: false,
			}, () => tools.run(interpreterPath!, ['-m', 'pip', 'install', '-U', 'q2lsp'], { encoding: 'utf8', timeout: 600000 }));
			if (!await checkEnvironment(interpreterPath)) {
				throw new Error('q2lsp is still missing after installation. Check the log, then retry this step.');
			}
		}
		await openStep('finish');
	};

	const finishSetup = async (): Promise<void> => {
		if (!interpreterPath) {
			await chooseEnvironment();
		}
		if (!interpreterPath) {
			return;
		}
		if (!await checkEnvironment(interpreterPath)) {
			await openStep('server');
			return;
		}
		const scopes = [
			{ label: 'Workspace', description: 'Use for this project', target: vscode.ConfigurationTarget.Workspace },
			{ label: 'User', description: 'Use as your default environment', target: vscode.ConfigurationTarget.Global },
		];
		const scope = await vscode.window.showQuickPick(
			vscode.workspace.workspaceFolders?.length ? scopes : scopes.slice(1),
			{ title: 'Save your QIIME 2 environment', placeHolder: interpreterPath },
		);
		if (!scope) {
			return;
		}
		await vscode.workspace.getConfiguration('q2lsp').update('interpreterPath', interpreterPath, scope.target);
		await progress(true, true, true);
		void vscode.window.showInformationMessage('Setup saved. Open a shell script to use q2lsp.');
	};

	const run = (action: () => Promise<void>) => async (): Promise<void> => {
		if (busy) {
			return;
		}
		if (!vscode.workspace.isTrusted) {
			const selection = await vscode.window.showWarningMessage(
				'Setup runs Python and environment tools. Trust this workspace to continue.', 'Manage Workspace Trust',
			);
			if (selection) {
				await manageWorkspaceTrust();
			}
			return;
		}
		busy = true;
		try {
			await action();
		} catch (error) {
			output.appendLine(String(error));
			const selection = await vscode.window.showErrorMessage(
				error instanceof Error ? error.message : String(error), 'Show Log',
			);
			if (selection) {
				output.show(true);
			}
		} finally {
			busy = false;
		}
	};
	context.subscriptions.push(
		vscode.commands.registerCommand('q2lsp.openSetupWizard', async () => {
			if (!interpreterPath && !busy) {
				await progress();
			}
			await openStep();
		}),
		vscode.commands.registerCommand('q2lsp.setupEnvironment', run(chooseEnvironment)),
		vscode.commands.registerCommand('q2lsp.setupServer', run(prepareServer)),
		vscode.commands.registerCommand('q2lsp.finishSetup', run(finishSetup)),
	);
};
