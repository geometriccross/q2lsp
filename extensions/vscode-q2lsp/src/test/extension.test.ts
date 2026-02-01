import * as assert from 'assert';
import {
	buildInterpreterCandidates,
	buildInterpreterPathNotAbsoluteMessage,
	buildServerCommand,
	DEFAULT_PATH_CANDIDATES,
	getUnsupportedPlatformMessage,
	isAbsolutePath,
	mergeEnv,
} from '../helpers';

suite('q2lsp helper tests', () => {
	test('interpreterPath overrides everything', () => {
		const candidates = buildInterpreterCandidates('/opt/python', '/opt/python-ext', DEFAULT_PATH_CANDIDATES);
		assert.deepStrictEqual(candidates, [{ path: '/opt/python', source: 'config' }]);
	});

	test('path fallback order prefers python3 then python', () => {
		const candidates = buildInterpreterCandidates(undefined, undefined, DEFAULT_PATH_CANDIDATES);
		assert.deepStrictEqual(candidates, [
			{ path: 'python3', source: 'path' },
			{ path: 'python', source: 'path' },
		]);
	});

	test('env merge prefers overrides', () => {
		const merged = mergeEnv({ FOO: 'base', BAR: 'base' }, { BAR: 'override', BAZ: 'override' });
		assert.deepStrictEqual(merged, { FOO: 'base', BAR: 'override', BAZ: 'override' });
	});

	test('windows platform is blocked', () => {
		assert.ok(getUnsupportedPlatformMessage('win32'));
		assert.strictEqual(getUnsupportedPlatformMessage('linux'), undefined);
	});

	test('server command uses q2lsp stdio', () => {
		assert.deepStrictEqual(buildServerCommand('/opt/python'), {
			command: '/opt/python',
			args: ['-m', 'q2lsp', '--transport', 'stdio'],
		});
	});

	test('absolute path detection', () => {
		assert.strictEqual(isAbsolutePath('/usr/bin/python3'), true);
		assert.strictEqual(isAbsolutePath('python3'), false);
	});

	test('non-absolute interpreter message is actionable', () => {
		const message = buildInterpreterPathNotAbsoluteMessage('python3');
		assert.ok(message.includes('python3'));
		assert.ok(message.includes('absolute'));
	});
});
