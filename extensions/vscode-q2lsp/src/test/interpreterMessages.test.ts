import * as assert from 'assert';
import {
	buildDiagnoseInterpreterValidationMessage,
	buildInterpreterPathNotAbsoluteMessage,
	buildInterpreterValidationMessage,
	formatOutputSnippet,
	Q2CLI_MISSING_QIIME_HINT,
	QIIME2_QUICKSTART_URL,
} from '../interpreterMessages';

suite('q2lsp interpreter message tests', () => {
	test('formatOutputSnippet returns <empty> for undefined or whitespace', () => {
		assert.strictEqual(formatOutputSnippet(undefined), '<empty>');
		assert.strictEqual(formatOutputSnippet('   \n\t  '), '<empty>');
	});

	test('formatOutputSnippet truncates values longer than 400 chars and appends ellipsis', () => {
		const longText = 'a'.repeat(401);
		const formatted = formatOutputSnippet(longText);
		assert.strictEqual(formatted.length, 403);
		assert.strictEqual(formatted, `${'a'.repeat(400)}...`);
	});

	test('formatOutputSnippet returns short non-empty values unchanged', () => {
		assert.strictEqual(formatOutputSnippet('hello output'), 'hello output');
	});

	test('non-absolute interpreter message is actionable', () => {
		const message = buildInterpreterPathNotAbsoluteMessage();
		assert.strictEqual(
			message,
			'q2lsp.interpreterPath must be absolute (e.g., /usr/bin/python3).'
		);
	});

	test('validation message includes missing modules', () => {
		const message = buildInterpreterValidationMessage('/opt/python', ['q2lsp', 'q2cli']);
		assert.ok(message.includes('q2lsp'));
		assert.ok(message.includes('q2cli'));
		assert.ok(message.includes('Required modules missing'));
		assert.ok(message.includes('QIIME 2 is not installed in this Python environment'));
		assert.ok(message.includes(QIIME2_QUICKSTART_URL));
		assert.ok(!message.includes('README'));
	});

	test('diagnose validation message keeps generic fallback without duplicate formatting', () => {
		assert.strictEqual(
			buildDiagnoseInterpreterValidationMessage(undefined),
			"q2lsp couldn't validate this interpreter. See q2lsp log for details."
		);
		assert.strictEqual(
			buildDiagnoseInterpreterValidationMessage(['q2lsp']),
			'Required modules missing: q2lsp.'
		);
	});

	test('q2cli hint points to QIIME 2 quickstart', () => {
		assert.ok(Q2CLI_MISSING_QIIME_HINT.includes(QIIME2_QUICKSTART_URL));
		assert.ok(!Q2CLI_MISSING_QIIME_HINT.includes('README'));
	});
});
