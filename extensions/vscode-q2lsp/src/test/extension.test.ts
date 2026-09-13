import * as assert from 'assert';
import * as vscode from 'vscode';
import { activate, deactivate } from '../extension';

suite('q2lsp extension tests', () => {
	test('the setup command opens the native walkthrough and its steps can be updated', async function () {
		this.timeout(10000);
		const id = 'geometriccross.qiime-language-server';
		const extension = vscode.extensions.getExtension(id);
		assert.ok(extension);
		await extension.activate();
		await vscode.commands.executeCommand('workbench.action.closeAllEditors');
		await vscode.commands.executeCommand('q2lsp.openSetupWizard');
		for (let attempt = 0; !vscode.window.tabGroups.activeTabGroup.activeTab && attempt < 20; attempt++) {
			await new Promise((resolve) => setTimeout(resolve, 50));
		}
		const tab = vscode.window.tabGroups.activeTabGroup.activeTab;
		assert.ok(tab);
		assert.ok(tab.label === 'Welcome' || tab.label.startsWith('Walkthrough:'));
		assert.ok(!(tab.input instanceof vscode.TabInputWebview), 'setup must use the native Getting Started editor');
		for (const step of ['environment', 'server', 'finish']) {
			const stepId = `${id}#q2lsp.setup#${step}`;
			await vscode.commands.executeCommand('welcome.markStepComplete', stepId);
			await vscode.commands.executeCommand('welcome.markStepIncomplete', stepId);
		}
		await vscode.commands.executeCommand('workbench.action.closeActiveEditor');
	});

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
