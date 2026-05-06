import * as vscode from 'vscode';
import { confirmAndInstallQ2lsp, selectPythonInterpreter } from './diagnosis';

export const SETUP_WIZARD_ACTIONS = [
	{
		command: 'installQ2lsp',
		label: 'Install q2lsp',
		description: 'Install q2lsp into the selected Python interpreter.',
	},
	{
		command: 'selectPythonInterpreter',
		label: 'Select Python Interpreter',
		description: 'Open the Python extension interpreter picker.',
	},
	{
		command: 'showQ2lspLog',
		label: 'Show q2lsp Log',
		description: 'Open the q2lsp output channel.',
	},
] as const;

type SetupWizardActionCommand = (typeof SETUP_WIZARD_ACTIONS)[number]['command'];

type SetupWizardMessage = {
	command?: unknown;
	interpreterPath?: unknown;
};

type SetupWizardOptions = {
	nonce: string;
	interpreterPath?: string;
};

let currentPanel: vscode.WebviewPanel | undefined;

export const openSetupWizard = (params: {
	context: vscode.ExtensionContext;
	outputChannel?: vscode.OutputChannel;
	interpreterPath?: string;
}): void => {
	const { context, outputChannel, interpreterPath } = params;
	if (currentPanel) {
		currentPanel.reveal(vscode.ViewColumn.One);
		currentPanel.webview.html = buildSetupWizardHtml({
			nonce: createNonce(),
			interpreterPath,
		});
		return;
	}

	const panel = vscode.window.createWebviewPanel(
		'q2lspSetupWizard',
		'q2lsp Setup Wizard',
		vscode.ViewColumn.One,
		{
			enableScripts: true,
		}
	);
	currentPanel = panel;
	panel.webview.html = buildSetupWizardHtml({
		nonce: createNonce(),
		interpreterPath,
	});

	const messageDisposable = panel.webview.onDidReceiveMessage(
		async (message: SetupWizardMessage) => {
			await handleSetupWizardMessage({
				message,
				outputChannel,
			});
		}
	);
	panel.onDidDispose(() => {
		messageDisposable.dispose();
		currentPanel = undefined;
	});
	context.subscriptions.push(panel);
};

export const buildSetupWizardHtml = (options: SetupWizardOptions): string => {
	const interpreterPath = escapeHtml(options.interpreterPath ?? '');
	const actions = SETUP_WIZARD_ACTIONS.map(
		(action) => `
			<button type="button" class="action" data-command="${action.command}">
				<span class="action-label">${escapeHtml(action.label)}</span>
				<span class="action-description">${escapeHtml(action.description)}</span>
			</button>`
	).join('');

	return `<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${options.nonce}';">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>q2lsp Setup Wizard</title>
	<style>
		body {
			color: var(--vscode-foreground);
			background: var(--vscode-editor-background);
			font-family: var(--vscode-font-family);
			font-size: var(--vscode-font-size);
			margin: 0;
			padding: 24px;
		}
		main {
			max-width: 760px;
		}
		h1 {
			font-size: 22px;
			font-weight: 600;
			margin: 0 0 16px;
		}
		label {
			display: block;
			font-weight: 600;
			margin-bottom: 6px;
		}
		input {
			background: var(--vscode-input-background);
			border: 1px solid var(--vscode-input-border);
			color: var(--vscode-input-foreground);
			box-sizing: border-box;
			font: inherit;
			margin-bottom: 18px;
			padding: 7px 9px;
			width: 100%;
		}
		.actions {
			display: grid;
			gap: 10px;
		}
		.action {
			align-items: flex-start;
			background: var(--vscode-button-secondaryBackground);
			border: 1px solid var(--vscode-button-border, transparent);
			color: var(--vscode-button-secondaryForeground);
			cursor: pointer;
			display: flex;
			flex-direction: column;
			font: inherit;
			padding: 10px 12px;
			text-align: left;
		}
		.action:hover {
			background: var(--vscode-button-secondaryHoverBackground);
		}
		.action-label {
			font-weight: 600;
		}
		.action-description {
			color: var(--vscode-descriptionForeground);
			margin-top: 3px;
		}
	</style>
</head>
<body>
	<main>
		<h1>q2lsp Setup Wizard</h1>
		<label for="interpreterPath">Python interpreter path</label>
		<input id="interpreterPath" type="text" value="${interpreterPath}" placeholder="/path/to/python">
		<div class="actions">
			${actions}
		</div>
	</main>
	<script nonce="${options.nonce}">
		const vscode = acquireVsCodeApi();
		const interpreterPathInput = document.getElementById('interpreterPath');
		for (const button of document.querySelectorAll('[data-command]')) {
			button.addEventListener('click', () => {
				vscode.postMessage({
					command: button.dataset.command,
					interpreterPath: interpreterPathInput.value,
				});
			});
		}
	</script>
</body>
</html>`;
};

const handleSetupWizardMessage = async (params: {
	message: SetupWizardMessage;
	outputChannel?: vscode.OutputChannel;
}): Promise<void> => {
	const command = toSetupWizardActionCommand(params.message.command);
	if (!command) {
		return;
	}

	switch (command) {
		case 'installQ2lsp': {
			const interpreterPath = toNonEmptyString(params.message.interpreterPath);
			if (!interpreterPath) {
				vscode.window.showErrorMessage('Enter a Python interpreter path before installing q2lsp.');
				return;
			}
			await confirmAndInstallQ2lsp(interpreterPath, params.outputChannel);
			return;
		}
		case 'selectPythonInterpreter':
			await selectPythonInterpreter();
			return;
		case 'showQ2lspLog':
			params.outputChannel?.show(true);
			return;
	}
};

const toSetupWizardActionCommand = (value: unknown): SetupWizardActionCommand | undefined => {
	if (typeof value !== 'string') {
		return undefined;
	}
	return SETUP_WIZARD_ACTIONS.some((action) => action.command === value)
		? (value as SetupWizardActionCommand)
		: undefined;
};

const toNonEmptyString = (value: unknown): string | undefined => {
	return typeof value === 'string' && value.trim() ? value.trim() : undefined;
};

const escapeHtml = (value: string): string => {
	return value
		.replaceAll('&', '&amp;')
		.replaceAll('"', '&quot;')
		.replaceAll("'", '&#39;')
		.replaceAll('<', '&lt;')
		.replaceAll('>', '&gt;');
};

const createNonce = (): string => {
	const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
	let text = '';
	for (let index = 0; index < 32; index += 1) {
		text += possible.charAt(Math.floor(Math.random() * possible.length));
	}
	return text;
};
