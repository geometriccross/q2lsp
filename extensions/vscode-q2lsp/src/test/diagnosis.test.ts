import * as assert from 'assert';
import { buildRepairActions } from '../diagnosis';

suite('q2lsp diagnosis tests', () => {
	test('buildRepairActions includes install when q2lsp is missing', () => {
		const actions = buildRepairActions(['q2lsp']);

		assert.ok(actions.includes('Install q2lsp'));
	});

	test('buildRepairActions includes quickstart when q2cli is missing', () => {
		const actions = buildRepairActions(['q2cli']);

		assert.ok(actions.includes('Open QIIME 2 Quickstart'));
	});

	test('buildRepairActions includes readme when q2cli is not missing', () => {
		const actions = buildRepairActions(['q2lsp']);

		assert.ok(actions.includes('Open README'));
		assert.ok(!actions.includes('Open QIIME 2 Quickstart'));
	});

	test('buildRepairActions always includes core actions', () => {
		const actions = buildRepairActions(undefined);

		assert.ok(actions.includes('Select Python Interpreter'));
		assert.ok(actions.includes('Open Settings'));
		assert.ok(actions.includes('Show q2lsp Log'));
	});
});
