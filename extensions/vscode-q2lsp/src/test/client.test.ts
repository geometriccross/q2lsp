import * as assert from 'assert';
import { buildQ2lspClientOptions, buildQ2lspServerOptions } from '../client';

function assertExecutable(
	value:
		| import('vscode-languageclient/node').Executable
		| import('vscode-languageclient/node').NodeModule
): asserts value is import('vscode-languageclient/node').Executable {
	assert.ok('command' in value);
}

suite('q2lsp client tests', () => {
	test('server options use q2lsp stdio command', () => {
		const serverOptions = buildQ2lspServerOptions({ interpreterPath: '/usr/bin/python3' });

		if (!('run' in serverOptions) || !('debug' in serverOptions)) {
			assert.fail('Expected server options to include run and debug executables.');
		}

		assertExecutable(serverOptions.run);
		assertExecutable(serverOptions.debug);
		assert.notStrictEqual(serverOptions.run, serverOptions.debug);

		assert.strictEqual(serverOptions.run.command, '/usr/bin/python3');
		assert.deepStrictEqual(serverOptions.run.args, ['-m', 'q2lsp', '--transport', 'stdio']);
		assert.strictEqual(serverOptions.debug.command, '/usr/bin/python3');
		assert.deepStrictEqual(serverOptions.debug.args, ['-m', 'q2lsp', '--transport', 'stdio']);
	});

	test('server options merge env overrides', () => {
		const key = 'Q2LSP_CLIENT_TEST_ENV';
		const previous = process.env[key];
		process.env[key] = 'base';

		try {
			const serverOptions = buildQ2lspServerOptions({
				interpreterPath: '/usr/bin/python3',
				serverEnv: {
					[key]: 'override',
					Q2LSP_CLIENT_TEST_ADDED: 'added',
				},
			});

			if (!('run' in serverOptions) || !('debug' in serverOptions)) {
				assert.fail('Expected server options to include run and debug executables.');
			}

			assert.strictEqual(serverOptions.run.options?.env?.[key], 'override');
			assert.strictEqual(serverOptions.run.options?.env?.Q2LSP_CLIENT_TEST_ADDED, 'added');
			assert.strictEqual(serverOptions.debug.options?.env?.[key], 'override');
			assert.strictEqual(serverOptions.debug.options?.env?.Q2LSP_CLIENT_TEST_ADDED, 'added');
		} finally {
			if (previous === undefined) {
				delete process.env[key];
			} else {
				process.env[key] = previous;
			}
		}
	});

	test('client options include shellscript selector', () => {
		const clientOptions = buildQ2lspClientOptions();
		assert.deepStrictEqual(clientOptions.documentSelector, [{ language: 'shellscript', scheme: 'file' }]);
	});
});
