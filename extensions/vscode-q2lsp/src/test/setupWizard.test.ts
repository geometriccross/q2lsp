import * as assert from 'assert';
import { mkdtemp, rm, writeFile } from 'fs/promises';
import { tmpdir } from 'os';
import * as path from 'path';
import * as vscode from 'vscode';
import { registerSetupWizard } from '../setupWizard/index';
import type { SetupTools } from '../setupWizard/environment';
import type { InterpreterValidationDetails } from '../interpreter';

suite('q2lsp setup walkthrough', () => {
	const originalWindow = {
		showQuickPick: vscode.window.showQuickPick,
		showOpenDialog: vscode.window.showOpenDialog,
		showWarningMessage: vscode.window.showWarningMessage,
		showErrorMessage: vscode.window.showErrorMessage,
		showInformationMessage: vscode.window.showInformationMessage,
		withProgress: vscode.window.withProgress,
	};
	const originalCommands = {
		registerCommand: vscode.commands.registerCommand,
		executeCommand: vscode.commands.executeCommand,
	};
	const originalConfiguration = vscode.workspace.getConfiguration;
	const originalGetExtension = vscode.extensions.getExtension;
	const originalOpenExternal = vscode.env.openExternal;
	const trustDescriptor = Object.getOwnPropertyDescriptor(vscode.workspace, 'isTrusted')!;
	const foldersDescriptor = Object.getOwnPropertyDescriptor(vscode.workspace, 'workspaceFolders')!;
	let handlers: Map<string, () => Promise<void>>;
	let completed: Map<string, boolean>;
	let choices: Array<string | undefined>;
	let confirmations: Array<string | undefined>;
	let warningDetails: string[];
	let dialogs: vscode.Uri[] | undefined;
	let errors: string[];
	let messages: string[];
	let logs: string[];
	let openedUrls: string[];
	let selectedSteps: string[];
	let checkedPaths: string[];
	let calls: Array<{ file: string; args: string[] }>;
	let saves: string[];
	let pickerLabels: string[][];
	let configured: string | undefined;
	let trusted: boolean;
	let tools: SetupTools;
	let token: vscode.CancellationTokenSource;

	const details = (missing: string[] = [], executable = '/qiime/bin/python'): InterpreterValidationDetails => ({
		missing, executable, version: '3.10',
	});
	const command = (name: string): Promise<void> => handlers.get(`q2lsp.${name}`)!();
	const progress = (): boolean[] => ['environment', 'server', 'finish'].map((step) => completed.get(step) ?? false);

	setup(async () => {
		handlers = new Map();
		completed = new Map();
		choices = [];
		confirmations = [];
		warningDetails = [];
		dialogs = undefined;
		errors = [];
		messages = [];
		logs = [];
		openedUrls = [];
		selectedSteps = [];
		checkedPaths = [];
		calls = [];
		saves = [];
		pickerLabels = [];
		configured = undefined;
		trusted = true;
		token = new vscode.CancellationTokenSource();
		Object.defineProperties(vscode.workspace, {
			isTrusted: { configurable: true, get: () => trusted },
			workspaceFolders: { configurable: true, get: () => undefined },
		});
		Object.assign(vscode.window, {
			showQuickPick: async (items: vscode.QuickPickItem[]) => {
				pickerLabels.push(items.map((item) => item.label));
				const choice = choices.shift();
				return items.find((item) => item.label === choice);
			},
			showOpenDialog: async () => dialogs,
			showWarningMessage: async (_message: string, options?: vscode.MessageOptions | string) => {
				if (typeof options === 'object' && options.detail) {
					warningDetails.push(options.detail);
				}
				return confirmations.shift();
			},
			showErrorMessage: async (message: string) => { errors.push(message); return undefined; },
			showInformationMessage: async (message: string) => { messages.push(message); return undefined; },
			withProgress: async <T>(_options: vscode.ProgressOptions, task: (progress: vscode.Progress<{ message?: string }>, token: vscode.CancellationToken) => Thenable<T>) => task({ report: () => undefined }, token.token),
		});
		Object.assign(vscode.commands, {
			registerCommand: (id: string, handler: () => Promise<void>) => {
				handlers.set(id, handler);
				return new vscode.Disposable(() => handlers.delete(id));
			},
			executeCommand: async (id: string, argument: string | { step: string }) => {
				if (id === 'workbench.action.openWalkthrough') {
					selectedSteps.push((argument as { step: string }).step);
				} else if (id === 'welcome.markStepComplete' || id === 'welcome.markStepIncomplete') {
					completed.set((argument as string).split('#').at(-1)!, id === 'welcome.markStepComplete');
				}
			},
		});
		Object.assign(vscode.workspace, {
			getConfiguration: () => ({
				get: (key: string) => key === 'interpreterPath' ? configured : undefined,
				update: async (_key: string, value: string) => { saves.push(value); configured = value; },
			}),
		});
		Object.assign(vscode.extensions, { getExtension: () => undefined });
		Object.assign(vscode.env, { openExternal: async (uri: vscode.Uri) => { openedUrls.push(uri.toString()); return true; } });
		tools = {
			check: async (path) => { checkedPaths.push(path); return details(['q2lsp']); },
			run: async (file, args) => {
				calls.push({ file, args });
				return JSON.stringify({ envs: ['/created/qiime2-tiny-2026.4'] });
			},
			environments: async () => [{
				version: '2026.4', distribution: 'tiny', platform: process.platform === 'darwin' ? 'osx-64' : 'linux-64',
				fileName: 'tiny.yml', environmentName: 'qiime2-tiny-2026.4',
				url: 'https://packages.qiime2.org/qiime2/2026.4/tiny/released/tiny.yml',
			}],
		};
		await registerSetupWizard({
			extension: { id: 'geometriccross.qiime-language-server' }, subscriptions: [],
		} as unknown as vscode.ExtensionContext, {
			appendLine: (line: string) => logs.push(line), show: () => undefined,
		} as unknown as vscode.OutputChannel, tools);
	});

	teardown(() => {
		token.dispose();
		Object.assign(vscode.window, originalWindow);
		Object.assign(vscode.commands, originalCommands);
		Object.assign(vscode.workspace, { getConfiguration: originalConfiguration });
		Object.defineProperty(vscode.workspace, 'isTrusted', trustDescriptor);
		Object.defineProperty(vscode.workspace, 'workspaceFolders', foldersDescriptor);
		Object.assign(vscode.extensions, { getExtension: originalGetExtension });
		Object.assign(vscode.env, { openExternal: originalOpenExternal });
	});

	test('opening the walkthrough does not probe Python, fetch metadata, or install anything', async () => {
		tools.environments = async () => assert.fail('opening must not fetch metadata');
		await command('openSetupWizard');
		assert.deepStrictEqual(selectedSteps, ['environment']);
		assert.deepStrictEqual(checkedPaths, []);
		assert.deepStrictEqual(calls, []);
		assert.deepStrictEqual(progress(), [false, false, false]);
	});

	test('existing environment is validated and the next necessary step is selected', async () => {
		tools.environments = async () => assert.fail('existing environments need no network');
		choices.push('python3');
		await command('setupEnvironment');
		assert.deepStrictEqual(checkedPaths, ['python3']);
		assert.deepStrictEqual(progress(), [true, false, false]);
		assert.deepStrictEqual(selectedSteps, ['server']);
		assert.deepStrictEqual(saves, []);
		assert.deepStrictEqual(messages, []);
	});

	test('successful checks save the resolved absolute interpreter, not a PATH alias', async () => {
		tools.check = async (path) => { checkedPaths.push(path); return details(); };
		choices.push('python3', 'User');
		await command('setupEnvironment');
		assert.deepStrictEqual(progress(), [true, true, false]);
		await command('finishSetup');
		assert.deepStrictEqual(checkedPaths, ['python3', '/qiime/bin/python']);
		assert.deepStrictEqual(saves, ['/qiime/bin/python']);
		assert.deepStrictEqual(progress(), [true, true, true]);
		assert.deepStrictEqual(pickerLabels.at(-1), ['User']);
	});

	test('choosing another interpreter invalidates all previous completion', async () => {
		tools.check = async () => details();
		choices.push('python3', 'User');
		await command('setupEnvironment');
		await command('finishSetup');
		tools.check = async () => details(['qiime2', 'q2cli'], '/other/bin/python');
		choices.push('Browse for Python…');
		dialogs = [vscode.Uri.file('/other/bin/python')];
		await command('setupEnvironment');
		assert.deepStrictEqual(progress(), [false, false, false]);
		assert.ok(errors[0].includes('Missing qiime2, q2cli'));
		assert.deepStrictEqual(saves, ['/qiime/bin/python']);
	});

	test('cancelling selection or browsing preserves the current validated target', async () => {
		choices.push('python3');
		await command('setupEnvironment');
		choices.push(undefined, 'Browse for Python…');
		await command('setupEnvironment');
		await command('setupEnvironment');
		assert.deepStrictEqual(checkedPaths, ['python3']);
		assert.deepStrictEqual(progress(), [true, false, false]);
	});

	test('q2lsp installation is confirmed, targets the selected interpreter, and is rechecked', async () => {
		choices.push('python3');
		await command('setupEnvironment');
		confirmations.push('Install q2lsp');
		tools.run = async (file, args) => {
			calls.push({ file, args });
			tools.check = async () => details();
			return '';
		};
		await command('setupServer');
		assert.deepStrictEqual(calls, [{ file: '/qiime/bin/python', args: ['-m', 'pip', 'install', '-U', 'q2lsp'] }]);
		assert.deepStrictEqual(progress(), [true, true, false]);
		assert.strictEqual(selectedSteps.at(-1), 'finish');
	});

	test('declining installation does not run pip or complete the step', async () => {
		choices.push('python3');
		await command('setupEnvironment');
		await command('setupServer');
		assert.deepStrictEqual(calls, []);
		assert.deepStrictEqual(progress(), [true, false, false]);
	});

	test('an install command exiting successfully is not proof that q2lsp is ready', async () => {
		choices.push('python3');
		confirmations.push('Install q2lsp');
		await command('setupServer');
		assert.deepStrictEqual(progress(), [true, false, false]);
		assert.ok(errors[0].includes('still missing'));
		tools.check = async () => details();
		await command('setupServer');
		assert.deepStrictEqual(progress(), [true, true, false]);
	});

	test('failed checks prevent installing and saving', async () => {
		choices.push('python3');
		tools.check = async () => details(['qiime2', 'q2cli']);
		await command('setupServer');
		await command('finishSetup');
		assert.deepStrictEqual(calls, []);
		assert.deepStrictEqual(saves, []);
		assert.deepStrictEqual(progress(), [false, false, false]);
	});

	test('a failed recheck clears previous completion, and saving requires another successful check', async () => {
		tools.check = async () => details();
		choices.push('python3');
		await command('setupEnvironment');
		tools.check = async () => { throw new Error('Python is no longer available'); };
		await command('finishSetup');
		assert.deepStrictEqual(saves, []);
		assert.deepStrictEqual(progress(), [false, false, false]);
		assert.ok(errors[0].includes('no longer available'));
	});

	test('cancelling save leaves the final step incomplete', async () => {
		tools.check = async () => details();
		choices.push('python3');
		await command('finishSetup');
		assert.deepStrictEqual(saves, []);
		assert.deepStrictEqual(progress(), [true, true, false]);
	});

	test('Conda creation requires confirmation and validates the created interpreter', async () => {
		choices.push('Create a QIIME 2 environment…', 'Conda / Miniconda', 'tiny');
		confirmations.push('Create Environment');
		await command('setupEnvironment');
		assert.deepStrictEqual(calls.map((call) => call.args[0]), ['--version', 'env', 'env']);
		assert.deepStrictEqual(checkedPaths, ['/created/qiime2-tiny-2026.4/bin/python']);
		assert.deepStrictEqual(progress(), [true, false, false]);
		assert.strictEqual(messages.length, 1);
		assert.ok(messages[0].includes('conda activate qiime2-tiny-2026.4'));
		assert.ok(logs.includes(messages[0]));
	});

	for (const qiimeReady of [true, false]) {
		test(`Pixi activation instructions ${qiimeReady ? 'use the validated default environment' : 'are not shown after a failed check'}`, async () => {
			const originalFetch = globalThis.fetch;
			const project = await mkdtemp(path.join(tmpdir(), 'q2lsp-wizard-pixi-'));
			const environmentName = 'qiime2-tiny-2026.4';
			const prefix = path.join(project, '.pixi', 'envs', 'default');
			const manifest = '[workspace]\nname = "existing-project"\nchannels = ["conda-forge"]\nplatforms = ["linux-64"]\n';
			try {
				await writeFile(path.join(project, 'pixi.toml'), manifest);
				globalThis.fetch = async () => new Response('name: qiime\ndependencies: [python, qiime2, q2cli]\n');
				tools.run = async (file, args) => {
					calls.push({ file, args });
					return JSON.stringify({ environments_info: [
						{ name: 'default', prefix },
						{ name: environmentName, prefix: path.join(project, '.pixi', 'envs', environmentName) },
					] });
				};
				tools.check = async (candidate) => {
					assert.deepStrictEqual(messages, [], 'activation guidance must wait for validation');
					checkedPaths.push(candidate);
					return details(qiimeReady ? ['q2lsp'] : ['q2cli', 'q2lsp'], candidate);
				};
				dialogs = [vscode.Uri.file(project)];
				choices.push('Create a QIIME 2 environment…', 'Pixi', 'tiny');
				confirmations.push('Create Environment');
				await command('setupEnvironment');

				assert.ok(warningDetails[0].includes('replace the default environment'), 'replacing default must be disclosed before confirmation');
				assert.deepStrictEqual(calls.map((call) => call.args[0]), ['--version', 'import', 'workspace', 'install', 'info']);
				assert.deepStrictEqual(calls[3], { file: 'pixi', args: ['install', '-e', 'default'] });
				assert.deepStrictEqual(checkedPaths, [path.join(prefix, 'bin', 'python')]);
				if (qiimeReady) {
					assert.strictEqual(messages.length, 1);
					assert.ok(messages[0].includes(project), 'instructions must identify the Pixi project folder');
					assert.ok(messages[0].includes('"pixi shell"'));
					assert.ok(messages[0].includes('default'));
					assert.ok(!messages[0].includes(' -e '), 'default must not need an environment flag');
					assert.ok(logs.includes(messages[0]), 'instructions remain available in the output channel');
					assert.deepStrictEqual(progress(), [true, false, false]);
					assert.deepStrictEqual(selectedSteps, ['server']);
					assert.deepStrictEqual(errors, []);
				} else {
					assert.deepStrictEqual(messages, []);
					assert.deepStrictEqual(progress(), [false, false, false]);
					assert.ok(errors[0].includes('Missing q2cli'));
				}
			} finally {
				globalThis.fetch = originalFetch;
				await rm(project, { recursive: true, force: true });
			}
		});
	}

	test('cancelling creation runs no environment creation command', async () => {
		choices.push('Create a QIIME 2 environment…', 'Conda / Miniconda', 'tiny');
		await command('setupEnvironment');
		assert.deepStrictEqual(calls, [{ file: 'conda', args: ['--version'] }]);
		assert.deepStrictEqual(checkedPaths, []);
		assert.deepStrictEqual(messages, []);
		assert.deepStrictEqual(progress(), [false, false, false]);
	});

	test('declining Pixi creation does not replace the default environment', async () => {
		choices.push('Create a QIIME 2 environment…', 'Pixi', 'tiny');
		dialogs = [vscode.Uri.file('/existing-pixi-project')];
		await command('setupEnvironment');
		assert.ok(warningDetails[0].includes('replace the default environment'));
		assert.deepStrictEqual(calls, [{ file: 'pixi', args: ['--version'] }]);
		assert.deepStrictEqual(checkedPaths, []);
		assert.deepStrictEqual(messages, []);
	});

	test('manual setup opens documentation without falsely completing a step', async () => {
		choices.push('Create a QIIME 2 environment…', 'Manual setup');
		await command('setupEnvironment');
		assert.strictEqual(openedUrls.length, 1);
		assert.deepStrictEqual(calls, []);
		assert.deepStrictEqual(progress(), [false, false, false]);
	});

	test('unavailable metadata does not generate a guessed installation command', async () => {
		tools.environments = async () => [];
		choices.push('Create a QIIME 2 environment…', 'Conda / Miniconda');
		await command('setupEnvironment');
		assert.deepStrictEqual(calls, [{ file: 'conda', args: ['--version'] }]);
		assert.ok(errors[0].includes('Could not load'));
	});

	test('a second setup action cannot overlap an active check', async () => {
		let resolveCheck!: (value: InterpreterValidationDetails) => void;
		tools.check = () => new Promise((resolve) => { resolveCheck = resolve; });
		choices.push('python3');
		const first = command('setupEnvironment');
		while (!resolveCheck) {
			await new Promise((resolve) => setTimeout(resolve, 0));
		}
		await command('setupServer');
		resolveCheck(details(['q2lsp']));
		await first;
		assert.deepStrictEqual(calls, []);
		assert.strictEqual(pickerLabels.length, 1);
	});

	test('untrusted workspaces can view the wizard but cannot run setup tools', async () => {
		trusted = false;
		await command('openSetupWizard');
		await command('setupEnvironment');
		await command('setupServer');
		await command('finishSetup');
		assert.deepStrictEqual(selectedSteps, ['environment']);
		assert.deepStrictEqual(checkedPaths, []);
		assert.deepStrictEqual(calls, []);
		assert.deepStrictEqual(pickerLabels, []);
	});
});
