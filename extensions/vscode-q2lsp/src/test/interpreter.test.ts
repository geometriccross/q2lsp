import * as assert from 'assert';
import { type ExecFileException } from 'child_process';
import { type ExecFileRunner, validateInterpreter } from '../interpreter';

suite('q2lsp interpreter tests', () => {
	test('validateInterpreter succeeds when required modules are available', async () => {
		let capturedFile = '';
		let capturedArgs: readonly string[] = [];
		const execRunner: ExecFileRunner = (file, args, options, callback) => {
			capturedFile = file;
			capturedArgs = args;
			assert.strictEqual(options.encoding, 'utf8');
			assert.strictEqual(options.timeout, 1234);
			callback(null, '{"missing":[],"executable":"/opt/python","version":"3.11.0"}', '');
		};

		const result = await validateInterpreter(execRunner, '/opt/python', 1234);

		assert.strictEqual(capturedFile, '/opt/python');
		assert.strictEqual(capturedArgs[0], '-c');
		assert.strictEqual(result.ok, true);
		assert.strictEqual(result.details?.executable, '/opt/python');
		assert.deepStrictEqual(result.details?.missing, []);
	});

	test('validateInterpreter reports missing modules from probe output', async () => {
		const execRunner: ExecFileRunner = (_file, _args, _options, callback) => {
			callback(null, '{"missing":["q2cli"],"executable":"/opt/python","version":"3.11.0"}', '');
		};

		const result = await validateInterpreter(execRunner, '/opt/python', 2000);

		assert.strictEqual(result.ok, false);
		assert.deepStrictEqual(result.missingModules, ['q2cli']);
		assert.strictEqual(result.details?.executable, '/opt/python');
	});

	test('validateInterpreter reports execution errors', async () => {
		const execRunner: ExecFileRunner = (_file, _args, _options, callback) => {
			const error = Object.assign(new Error('spawn ENOENT'), { code: 'ENOENT' }) as ExecFileException;
			callback(error, '', 'process failed');
		};

		const result = await validateInterpreter(execRunner, '/missing/python', 2000);

		assert.strictEqual(result.ok, false);
		assert.strictEqual(result.errorMessage, 'spawn ENOENT');
		assert.strictEqual(result.stderr, 'process failed');
	});
});
