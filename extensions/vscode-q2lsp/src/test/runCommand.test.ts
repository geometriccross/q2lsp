import * as assert from 'assert';
import {
	executeQiimeRunCommand,
	formatQiimeRunCommandTokens,
	resolveQiimeRunTerminal,
	toQiimeRunCommandPayload,
} from '../runCommand';

suite('q2lsp run command tests', () => {
	test('accepts token payload from CodeLens command arguments', () => {
		const payload = toQiimeRunCommandPayload({
			uri: 'file:///test.sh',
			commandText: 'qiime feature-table summarize --i-table "$TABLE"',
			tokens: ['qiime', 'feature-table', 'summarize', '--i-table', 'table.qza'],
		});

		assert.deepStrictEqual(payload, {
			uri: 'file:///test.sh',
			commandText: 'qiime feature-table summarize --i-table "$TABLE"',
			tokens: ['qiime', 'feature-table', 'summarize', '--i-table', 'table.qza'],
		});
		assert.strictEqual(
			payload && formatQiimeRunCommandTokens(payload),
			'["qiime","feature-table","summarize","--i-table","table.qza"]'
		);
	});

	test('rejects malformed CodeLens command arguments', () => {
		assert.strictEqual(toQiimeRunCommandPayload(undefined), undefined);
		assert.strictEqual(
			toQiimeRunCommandPayload({
				uri: 'file:///test.sh',
				commandText: 'qiime info',
				tokens: ['qiime', 1],
			}),
			undefined
		);
		assert.strictEqual(
			toQiimeRunCommandPayload({ uri: 'file:///test.sh', tokens: ['qiime'] }),
			undefined
		);
		assert.strictEqual(
			toQiimeRunCommandPayload({
				uri: 'file:///test.sh',
				commandText: ['qiime info'],
				tokens: ['qiime'],
			}),
			undefined
		);
	});

	test('sends raw command text to the terminal for shell expansion', () => {
		const sentText: string[] = [];
		let shown = false;

		executeQiimeRunCommand(
			{
				uri: 'file:///test.sh',
				commandText: 'qiime feature-table summarize --i-table "$TABLE"',
				tokens: ['qiime', 'feature-table', 'summarize', '--i-table', '$TABLE'],
			},
			{
				sendText: (text) => sentText.push(text),
				show: () => {
					shown = true;
				},
			}
		);

		assert.deepStrictEqual(sentText, ['qiime feature-table summarize --i-table "$TABLE"']);
		assert.strictEqual(shown, true);
	});

	test('reuses active terminal when one exists', () => {
		const activeTerminal = {
			sendText: () => undefined,
			show: () => undefined,
		};
		const fallbackTerminal = {
			sendText: () => undefined,
			show: () => undefined,
		};
		let created = false;

		const terminal = resolveQiimeRunTerminal(
			activeTerminal,
			[fallbackTerminal],
			() => {
				created = true;
				return fallbackTerminal;
			}
		);

		assert.strictEqual(terminal, activeTerminal);
		assert.strictEqual(created, false);
	});

	test('reuses first existing terminal when no terminal is active', () => {
		const existingTerminal = {
			sendText: () => undefined,
			show: () => undefined,
		};
		let created = false;

		const terminal = resolveQiimeRunTerminal(
			undefined,
			[existingTerminal],
			() => {
				created = true;
				return existingTerminal;
			}
		);

		assert.strictEqual(terminal, existingTerminal);
		assert.strictEqual(created, false);
	});

	test('creates terminal only when no existing terminal is available', () => {
		const createdTerminal = {
			sendText: () => undefined,
			show: () => undefined,
		};
		let created = false;

		const terminal = resolveQiimeRunTerminal(
			undefined,
			[],
			() => {
				created = true;
				return createdTerminal;
			}
		);

		assert.strictEqual(terminal, createdTerminal);
		assert.strictEqual(created, true);
	});
});
