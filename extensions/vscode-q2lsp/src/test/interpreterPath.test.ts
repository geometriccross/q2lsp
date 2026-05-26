import * as assert from 'assert';
import { isAbsolutePath } from '../interpreterPath';

suite('q2lsp interpreter path tests', () => {
	test('absolute path detection', () => {
		assert.strictEqual(isAbsolutePath('/usr/bin/python3'), true);
		assert.strictEqual(isAbsolutePath('python3'), false);
	});
});
