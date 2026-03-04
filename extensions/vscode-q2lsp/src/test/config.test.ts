import * as assert from 'assert';
import { normalizeConfiguredInterpreterPath, sanitizeServerEnvOverrides } from '../config';

suite('q2lsp config tests', () => {
	test('normalizeConfiguredInterpreterPath trims and drops empty values', () => {
		assert.strictEqual(normalizeConfiguredInterpreterPath(undefined), undefined);
		assert.strictEqual(normalizeConfiguredInterpreterPath('   '), undefined);
		assert.strictEqual(normalizeConfiguredInterpreterPath(' /usr/bin/python3  '), '/usr/bin/python3');
	});

	test('sanitizeServerEnvOverrides keeps only string entries', () => {
		const sanitized = sanitizeServerEnvOverrides({
			Q2LSP_A: 'value',
			Q2LSP_B: 1,
			Q2LSP_C: true,
			Q2LSP_D: null,
			Q2LSP_E: 'another',
		});

		assert.deepStrictEqual(sanitized, {
			Q2LSP_A: 'value',
			Q2LSP_E: 'another',
		});
		assert.deepStrictEqual(sanitizeServerEnvOverrides(undefined), {});
		assert.deepStrictEqual(sanitizeServerEnvOverrides('not-an-object'), {});
	});
});
