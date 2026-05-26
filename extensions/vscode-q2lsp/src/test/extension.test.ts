import * as assert from 'assert';
import type * as vscode from 'vscode';
import { activate, deactivate } from '../extension';

suite('q2lsp extension tests', () => {
	test('activation stops before registering commands on native Windows', async () => {
		const originalPlatform = process.platform;
		Object.defineProperty(process, 'platform', { value: 'win32' });
		const context = { subscriptions: [] } as unknown as vscode.ExtensionContext;

		try {
			await activate(context);

			assert.strictEqual(context.subscriptions.length, 1);
		} finally {
			await deactivate();
			Object.defineProperty(process, 'platform', { value: originalPlatform });
		}
	});
});
