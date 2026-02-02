import * as assert from 'assert';
import {
	buildInterpreterCandidates,
	buildInterpreterPathNotAbsoluteMessage,
	buildInterpreterValidationMessage,
	buildInterpreterValidationSnippet,
	parseInterpreterValidationStdout,
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

	test('validation snippet checks for q2lsp and q2cli', () => {
		const snippet = buildInterpreterValidationSnippet();
		assert.ok(snippet.includes('q2lsp'));
		assert.ok(snippet.includes('q2cli'));
		assert.ok(snippet.includes('executable'));
		assert.ok(snippet.includes('find_spec'));
	});

	test('validation message includes missing modules', () => {
		const message = buildInterpreterValidationMessage('/opt/python', ['q2lsp', 'q2cli'], undefined);
		assert.ok(message.includes('q2lsp'));
		assert.ok(message.includes('q2cli'));
		assert.ok(message.includes('/opt/python'));
		assert.ok(message.includes('conda/pixi'));
	});

	test('validation stdout parse returns missing modules and executable', () => {
		const parsed = parseInterpreterValidationStdout(
			'{"missing":["q2lsp"],"executable":"/opt/python","version":"3.11.0"}'
		);
		assert.deepStrictEqual(parsed?.missing, ['q2lsp']);
		assert.strictEqual(parsed?.executable, '/opt/python');
	});

	test('validation stdout parse fails on unexpected output', () => {
		assert.strictEqual(parseInterpreterValidationStdout('WARNING: something'), null);
		assert.strictEqual(parseInterpreterValidationStdout(''), null);
	});
});
