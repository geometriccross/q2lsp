import * as assert from 'assert';
import * as vscode from 'vscode';
import { resolveInterpreter } from '../interpreter_resolver';
import * as interpreter from '../interpreter';

const context = { extensionUri: vscode.Uri.file('/') } as vscode.ExtensionContext;
const outputChannel = {
	appendLine: (_value: string) => undefined,
	show: () => undefined,
} as vscode.OutputChannel;

type MutableInterpreterModule = typeof interpreter & {
	validateInterpreter: typeof interpreter.validateInterpreter;
};

suite('q2lsp interpreter resolver tests', () => {
	let originalValidateInterpreter: typeof interpreter.validateInterpreter;
	let originalShowErrorMessage: typeof vscode.window.showErrorMessage;

	setup(() => {
		originalValidateInterpreter = interpreter.validateInterpreter;
		originalShowErrorMessage = vscode.window.showErrorMessage;
		(vscode.window as typeof vscode.window & { showErrorMessage: typeof vscode.window.showErrorMessage }).showErrorMessage = async () => undefined;
	});

	teardown(() => {
		(interpreter as MutableInterpreterModule).validateInterpreter = originalValidateInterpreter;
		(vscode.window as typeof vscode.window & { showErrorMessage: typeof vscode.window.showErrorMessage }).showErrorMessage = originalShowErrorMessage;
	});

	test('resolveInterpreter returns the first valid candidate when config provides a valid path', async () => {
		const validatedPaths: string[] = [];
		(interpreter as MutableInterpreterModule).validateInterpreter = async (_execFile, interpreterPath) => {
			validatedPaths.push(interpreterPath);
			return { ok: true };
		};

		const resolved = await resolveInterpreter({
			context,
			outputChannel,
			config: { interpreterPath: '/opt/q2/bin/python' },
		});

		assert.deepStrictEqual(resolved, { path: '/opt/q2/bin/python', source: 'config' });
		assert.deepStrictEqual(validatedPaths, ['/opt/q2/bin/python']);
	});

	test('resolveInterpreter returns undefined when all candidates fail validation', async () => {
		const validatedPaths: string[] = [];
		(interpreter as MutableInterpreterModule).validateInterpreter = async (_execFile, interpreterPath) => {
			validatedPaths.push(interpreterPath);
			return { ok: false, missingModules: ['q2lsp'] };
		};

		const resolved = await resolveInterpreter({
			context,
			outputChannel,
			config: {},
		});

		assert.strictEqual(resolved, undefined);
		assert.ok(validatedPaths.includes('python3'));
		assert.ok(validatedPaths.includes('python'));
	});
});
