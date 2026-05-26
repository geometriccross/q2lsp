import * as assert from 'assert';
import {
	DEFAULT_PATH_CANDIDATES,
	buildInterpreterCandidates,
} from '../interpreterSources';

suite('q2lsp interpreter source tests', () => {
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
});
