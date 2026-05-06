import { execFile, type ExecFileOptionsWithStringEncoding } from 'child_process';
import { mkdir } from 'fs/promises';
import * as vscode from 'vscode';
import { selectPythonInterpreter } from './diagnosis';
import { VALIDATION_TIMEOUT_MS, buildInterpreterValidationSnippet, parseInterpreterValidationStdout } from './helpers';
import { execFileForValidation, validateInterpreter } from './interpreter';

export const SETUP_WIZARD_FLOW_STEPS = [
	{ id: 'packageManager', label: '1 Package Manager' },
	{ id: 'installManager', label: '2 Install Manager' },
	{ id: 'installQiime', label: '3 Install QIIME' },
	{ id: 'installQ2lsp', label: '4 Install q2lsp' },
] as const;

export const SETUP_WIZARD_MANAGERS = [
	{
		id: 'conda',
		label: 'Conda / Miniforge',
		description: 'Recommended for QIIME 2',
		command: 'Open Miniforge installer before continuing',
	},
	{
		id: 'pixi',
		label: 'Pixi',
		description: 'Project-local reproducible setup',
		command: 'curl -fsSL https://pixi.sh/install.sh | sh',
	},
	{
		id: 'manual',
		label: 'Manual',
		description: 'Use your own setup and validate later',
		command: 'Open QIIME 2 Quickstart',
	},
] as const;

export const QIIME_DISTRIBUTIONS = ['amplicon', 'moshpit', 'pathogenome', 'tiny'] as const;

export const QIIME_VERSIONS = ['2026.4', '2026.1', '2025.10', '2025.7', '2025.4', '2024.10', '2024.5', '2024.2', '2023.9'] as const;

type QiimePlatform = {
	id: string;
	label: string;
	condaSubdir?: string;
};

type QiimeEnvironmentOption = {
	version: string;
	distribution: string;
	platform: string;
	fileName: string;
	url: string;
	environmentName: string;
};

type SetupWizardMessage = {
	command?: unknown;
	commandText?: unknown;
	interpreterPath?: unknown;
	manager?: unknown;
	environmentName?: unknown;
	environmentUrl?: unknown;
	condaSubdir?: unknown;
};

type SetupWizardOptions = {
	nonce: string;
	interpreterPath?: string;
	platform?: QiimePlatform;
	environments?: QiimeEnvironmentOption[];
};

export const QIIME_MANIFEST_TREE_URL =
	'https://api.github.com/repos/qiime2/distributions/git/trees/dev?recursive=1';
export const QIIME_MANIFEST_CONTENTS_URL =
	'https://api.github.com/repos/qiime2/distributions/contents';
export const QIIME_PACKAGES_BASE_URL = 'https://packages.qiime2.org/qiime2';
export const QIIME_QUICKSTART_URL = 'https://library.qiime2.org/quickstart/qiime2';
export const MINIFORGE_INSTALL_URL = 'https://github.com/conda-forge/miniforge#download';
export const PIXI_INSTALL_COMMAND = 'curl -fsSL https://pixi.sh/install.sh | sh';

let currentPanel: vscode.WebviewPanel | undefined;

export const openSetupWizard = (params: {
	context: vscode.ExtensionContext;
	outputChannel?: vscode.OutputChannel;
	interpreterPath?: string;
}): void => {
	const { context, outputChannel, interpreterPath } = params;
	const platform = resolveQiimePlatform(process.platform, process.arch);
	const fallbackEnvironments = buildFallbackQiimeEnvironments(platform);
	if (currentPanel) {
		currentPanel.reveal(vscode.ViewColumn.One);
		currentPanel.webview.html = buildSetupWizardHtml({
			nonce: createNonce(),
			interpreterPath,
			platform,
			environments: fallbackEnvironments,
		});
		void refreshQiimeManifest(currentPanel.webview, platform);
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
		platform,
		environments: fallbackEnvironments,
	});
	void refreshQiimeManifest(panel.webview, platform);

	const messageDisposable = panel.webview.onDidReceiveMessage(
		async (message: SetupWizardMessage) => {
			await handleSetupWizardMessage({
				message,
				outputChannel,
				webview: panel.webview,
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
	const initialInterpreterPath = options.interpreterPath ?? '';
	const platform = options.platform ?? resolveQiimePlatform(process.platform, process.arch);
	const environments = options.environments ?? buildFallbackQiimeEnvironments(platform);
	const stepButtons = SETUP_WIZARD_FLOW_STEPS.map(
		(step, index) => `
			<button type="button" class="step" data-step-index="${index}">
				<span class="step-index">${index + 1}</span>
				<span>${escapeHtml(step.label.replace(/^\d\s/, ''))}</span>
			</button>`
	).join('');
	const managerCards = SETUP_WIZARD_MANAGERS.map(
		(manager) => `
			<button type="button" class="option-card" data-manager="${manager.id}">
				<span class="option-title">${escapeHtml(manager.label)}</span>
				<span class="option-description">${escapeHtml(manager.description)}</span>
			</button>`
	).join('');
	const initialVersion = resolveInitialQiimeVersion(environments);
	const initialDistributions = uniqueQiimeDistributions(environments.filter(
		(environment) => environment.version === initialVersion && environment.platform === platform.id
	));
	const distributionOptions = initialDistributions.map(
		(distribution) => `<option value="${escapeHtml(distribution)}">${escapeHtml(distribution)}</option>`
	).join('');
	const initialVersions = uniqueQiimeVersions(environments);
	const versionOptions = initialVersions.map((version) => `<option value="${version}">${escapeHtml(version)}</option>`).join('');

	const bootstrapState = JSON.stringify({
		interpreterPath: initialInterpreterPath,
		versions: QIIME_VERSIONS,
		managers: SETUP_WIZARD_MANAGERS,
		platform,
		environments,
		initialVersion,
		initialDistribution: initialDistributions[0] ?? '',
	});

	return `<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${options.nonce}';">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>q2lsp Setup Wizard</title>
	<style>
		:root {
			color-scheme: dark;
		}
		body {
			color: var(--vscode-foreground);
			background: var(--vscode-editor-background);
			font-family: var(--vscode-font-family);
			font-size: var(--vscode-font-size);
			margin: 0;
		}
		button,
		select {
			font: inherit;
		}
		.shell {
			box-sizing: border-box;
			display: grid;
			gap: 18px;
			min-height: 100vh;
			padding: 22px 24px;
		}
		.header {
			border-bottom: 1px solid var(--vscode-widget-border);
			padding-bottom: 12px;
		}
		h1 {
			font-size: 20px;
			font-weight: 600;
			margin: 0 0 14px;
		}
		.steps {
			display: grid;
			gap: 8px;
			grid-template-columns: repeat(4, minmax(0, 1fr));
		}
		.step {
			align-items: center;
			background: transparent;
			border: 1px solid var(--vscode-widget-border);
			color: var(--vscode-descriptionForeground);
			cursor: pointer;
			display: flex;
			gap: 8px;
			min-height: 34px;
			padding: 5px 9px;
			text-align: left;
		}
		.step.is-active {
			border-color: var(--vscode-focusBorder);
			color: var(--vscode-foreground);
		}
		.step.is-complete {
			color: var(--vscode-testing-iconPassed);
		}
		.step-index {
			align-items: center;
			border: 1px solid currentColor;
			border-radius: 50%;
			display: inline-flex;
			height: 18px;
			justify-content: center;
			width: 18px;
		}
		.context-chips {
			display: flex;
			flex-wrap: wrap;
			gap: 6px;
			margin-top: 8px;
			min-height: 20px;
		}
		.chip {
			border: 1px solid var(--vscode-widget-border);
			border-radius: 999px;
			color: var(--vscode-descriptionForeground);
			font-size: 11px;
			line-height: 18px;
			padding: 0 8px;
		}
		.chip.success {
			border-color: color-mix(in srgb, var(--vscode-testing-iconPassed) 50%, transparent);
			color: var(--vscode-testing-iconPassed);
		}
		.chip.warning {
			border-color: color-mix(in srgb, var(--vscode-editorWarning-foreground) 55%, transparent);
			color: var(--vscode-editorWarning-foreground);
		}
		main {
			max-width: 860px;
		}
		.screen {
			display: grid;
			gap: 16px;
		}
		.screen[hidden] {
			display: none;
		}
		h2 {
			font-size: 18px;
			font-weight: 600;
			margin: 0;
		}
		.option-grid,
		.summary-grid {
			display: grid;
			gap: 10px;
		}
		.option-card {
			background: var(--vscode-sideBar-background);
			border: 1px solid var(--vscode-widget-border);
			color: var(--vscode-foreground);
			cursor: pointer;
			display: flex;
			flex-direction: column;
			gap: 3px;
			padding: 10px 12px;
			text-align: left;
		}
		.option-card.is-selected {
			border-color: var(--vscode-focusBorder);
			box-shadow: inset 3px 0 0 var(--vscode-focusBorder);
		}
		.option-title,
		.row-label {
			font-weight: 600;
		}
		.option-description,
		.row-value,
		.note {
			color: var(--vscode-descriptionForeground);
		}
		.field-row {
			display: grid;
			gap: 10px;
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
		label {
			display: grid;
			gap: 5px;
			font-weight: 600;
		}
		select {
			background: var(--vscode-dropdown-background);
			border: 1px solid var(--vscode-dropdown-border);
			color: var(--vscode-dropdown-foreground);
			padding: 6px 8px;
		}
		.summary-row {
			align-items: baseline;
			border-bottom: 1px solid var(--vscode-widget-border);
			display: grid;
			gap: 12px;
			grid-template-columns: 180px 1fr;
			padding: 8px 0;
		}
		.command-box {
			background: var(--vscode-textCodeBlock-background);
			border: 1px solid var(--vscode-widget-border);
			display: grid;
			gap: 8px;
			padding: 10px;
		}
		.status-line {
			border: 1px solid var(--vscode-widget-border);
			color: var(--vscode-descriptionForeground);
			min-height: 18px;
			padding: 8px 10px;
		}
		.status-line:empty {
			display: none;
		}
		code {
			color: var(--vscode-textPreformat-foreground);
			font-family: var(--vscode-editor-font-family);
			white-space: pre-wrap;
			word-break: break-word;
		}
		.progress {
			border: 1px solid var(--vscode-widget-border);
			display: grid;
		}
		.progress-row {
			align-items: center;
			border-bottom: 1px solid var(--vscode-widget-border);
			display: flex;
			gap: 8px;
			padding: 8px 10px;
		}
		.progress-row:last-child {
			border-bottom: 0;
		}
		.dot {
			background: var(--vscode-descriptionForeground);
			border-radius: 50%;
			height: 8px;
			width: 8px;
		}
		.dot.active {
			background: var(--vscode-focusBorder);
		}
		.dot.success {
			background: var(--vscode-testing-iconPassed);
		}
		.actions {
			align-items: center;
			display: flex;
			flex-wrap: wrap;
			gap: 8px;
			justify-content: flex-end;
		}
		.action {
			background: var(--vscode-button-secondaryBackground);
			border: 1px solid var(--vscode-button-border, transparent);
			color: var(--vscode-button-secondaryForeground);
			cursor: pointer;
			padding: 6px 11px;
		}
		.action.primary {
			background: var(--vscode-button-background);
			color: var(--vscode-button-foreground);
		}
		.action:disabled {
			cursor: not-allowed;
			opacity: 0.5;
		}
	</style>
</head>
<body>
	<div class="shell">
		<header class="header">
			<h1>q2lsp Setup Wizard</h1>
			<nav class="steps" aria-label="Setup flow">
				${stepButtons}
			</nav>
			<div class="context-chips" id="contextChips"></div>
		</header>
		<main>
			<section class="screen" data-screen="0">
				<h2>Choose package manager</h2>
				<div class="option-grid">
					${managerCards}
				</div>
				<div class="actions">
					<button type="button" class="action" data-command="selectPythonInterpreter">Select existing QIIME 2 interpreter</button>
					<button type="button" class="action primary" data-next>Continue</button>
				</div>
			</section>
			<section class="screen" data-screen="1" hidden>
				<h2 id="installManagerHeading">Install selected manager</h2>
				<div class="summary-grid">
					<div class="summary-row">
						<span class="row-label">Selected manager</span>
						<span class="row-value" id="selectedManagerLabel"></span>
					</div>
					<div class="summary-row">
						<span class="row-label">Status</span>
						<span class="row-value" id="managerStatus">Not installed</span>
					</div>
				</div>
				<div class="command-box">
					<code id="managerCommand"></code>
				</div>
				<div class="status-line" id="managerStatusMessage"></div>
				<div class="actions">
					<button type="button" class="action" data-back>Back</button>
					<button type="button" class="action" data-command="checkManager">I installed it, check again</button>
					<button type="button" class="action primary" id="installManagerPrimaryAction" data-command="installManager">Install in Terminal</button>
				</div>
			</section>
			<section class="screen" data-screen="2" hidden>
				<h2>Install QIIME 2 environment</h2>
				<div class="field-row">
					<label>
						Distribution
						<select id="distributionSelect">
							${distributionOptions}
						</select>
					</label>
					<label>
						Version
						<select id="versionSelect">
							${versionOptions}
						</select>
					</label>
				</div>
				<div class="summary-grid">
					<div class="summary-row">
						<span class="row-label">Manager</span>
						<span class="row-value" id="qiimeManagerLabel"></span>
					</div>
					<div class="summary-row">
						<span class="row-label">Platform</span>
						<span class="row-value" id="platformLabel"></span>
					</div>
					<div class="summary-row">
						<span class="row-label">Environment name</span>
						<span class="row-value" id="environmentName"></span>
					</div>
					<div class="summary-row">
						<span class="row-label">Environment file</span>
						<span class="row-value" id="environmentFile"></span>
					</div>
				</div>
				<div class="command-box">
					<code id="qiimeCommand"></code>
					<span class="note">Official environment file will be opened or downloaded before running.</span>
				</div>
				<div class="status-line" id="qiimeStatusMessage"></div>
				<div class="progress">
					<div class="progress-row"><span class="dot active" data-progress="createEnvironment"></span>Create environment</div>
					<div class="progress-row"><span class="dot" data-progress="qiimeInfo"></span>Run qiime info</div>
					<div class="progress-row"><span class="dot" data-progress="locateInterpreter"></span>Locate Python interpreter</div>
				</div>
				<div class="actions">
					<button type="button" class="action" data-back>Back</button>
					<button type="button" class="action" data-command="validateEnvironment">Validate Environment</button>
					<button type="button" class="action primary" data-command="createQiimeEnvironment">Create QIIME Environment</button>
				</div>
			</section>
			<section class="screen" data-screen="3" hidden>
				<h2>Install q2lsp</h2>
				<div class="command-box">
					<code id="q2lspCommand"></code>
					<span class="note">Installs only the language server package into the selected QIIME 2 environment.</span>
				</div>
				<div class="status-line" id="q2lspStatusMessage"></div>
				<div class="progress">
					<div class="progress-row"><span class="dot active" data-progress="installQ2lsp"></span>Install q2lsp</div>
					<div class="progress-row"><span class="dot" data-progress="validateQ2lsp"></span>Validate q2lsp import</div>
					<div class="progress-row"><span class="dot" data-progress="saveInterpreter"></span>Save q2lsp.interpreterPath</div>
					<div class="progress-row"><span class="dot"></span>Restart q2lsp server</div>
				</div>
				<div class="actions">
					<button type="button" class="action" data-back>Back</button>
					<button type="button" class="action" data-command="validateQ2lsp">Validate q2lsp</button>
					<button type="button" class="action" id="saveInterpreterPathAction" data-command="saveInterpreterPath" disabled>Save interpreter path</button>
					<button type="button" class="action" id="restartServerAction" data-command="restartServer" disabled>Restart q2lsp server</button>
					<button type="button" class="action primary" data-command="installQ2lsp">Install q2lsp</button>
				</div>
			</section>
		</main>
	</div>
	<script nonce="${options.nonce}">
		const vscode = acquireVsCodeApi();
		const bootstrap = ${bootstrapState};
		const state = {
			stepIndex: 0,
			manager: 'conda',
			distribution: bootstrap.initialDistribution,
			version: bootstrap.initialVersion,
			interpreterPath: bootstrap.interpreterPath,
			managerStatus: 'unknown',
			qiimeStatus: 'unknown',
			q2lspStatus: 'unknown',
			savedInterpreterPath: false,
			statusMessage: '',
			environments: bootstrap.environments,
			platform: bootstrap.platform,
		};
		const managerById = Object.fromEntries(bootstrap.managers.map((manager) => [manager.id, manager]));
		const uniqueValues = (values) => Array.from(new Set(values)).sort((left, right) =>
			right.localeCompare(left, undefined, { numeric: true })
		);
		const availableEnvironmentsForVersion = () => state.environments
			.filter((environment) => environment.version === state.version)
			.filter((environment) => environment.platform === state.platform.id);
		const firstEnvironmentForVersion = () => availableEnvironmentsForVersion()
			.sort((left, right) => left.distribution.localeCompare(right.distribution))[0];
		const normalizeDistributionForVersion = () => {
			const distributionsForVersion = new Set(availableEnvironmentsForVersion()
				.map((environment) => environment.distribution));
			if (!distributionsForVersion.has(state.distribution)) {
				state.distribution = firstEnvironmentForVersion()?.distribution || '';
			}
		};
		const updateSelectors = () => {
			const availableVersions = uniqueValues(state.environments
				.filter((environment) => environment.platform === state.platform.id)
				.map((environment) => environment.version));
			const versionSelect = document.getElementById('versionSelect');
			versionSelect.innerHTML = availableVersions
				.map((version) => '<option value="' + version + '">' + version + '</option>')
				.join('');
			if (!availableVersions.includes(state.version)) {
				state.version = availableVersions[0] || bootstrap.versions[0];
			}
			versionSelect.value = state.version;
			normalizeDistributionForVersion();

			const distributionsForVersion = new Set(availableEnvironmentsForVersion()
				.map((environment) => environment.distribution));
			const distributionSelect = document.getElementById('distributionSelect');
			distributionSelect.innerHTML = Array.from(distributionsForVersion).sort()
				.map((distribution) => '<option value="' + distribution + '">' + distribution + '</option>')
				.join('');
			normalizeDistributionForVersion();
			distributionSelect.value = state.distribution;
		};

		const selectedEnvironment = () => state.environments.find((environment) =>
			environment.distribution === state.distribution &&
			environment.version === state.version &&
			environment.platform === state.platform.id
		) || state.environments.find((environment) =>
			environment.version === state.version &&
			environment.platform === state.platform.id
		) || firstEnvironmentForVersion();
		const environmentName = () => selectedEnvironment()?.environmentName || '';
		const environmentFile = () => selectedEnvironment()?.fileName || '';
		const environmentUrl = () => selectedEnvironment()?.url || '';
		const inferredInterpreterPath = () => state.interpreterPath ||
			'/opt/miniforge/envs/' + environmentName() + '/bin/python';
		const qiimeCommand = () => {
			if (state.manager === 'pixi') {
				return 'mkdir -p .qiime2 && cd .qiime2 && pixi init --format pyproject && pixi import ' + environmentUrl();
			}
			if (state.manager === 'manual') {
				return 'Open QIIME 2 Quickstart, then return to validate the selected interpreter.';
			}
			const subdirPrefix = state.platform.condaSubdir ? 'CONDA_SUBDIR=' + state.platform.condaSubdir + ' ' : '';
			return subdirPrefix + 'conda env create --name ' + environmentName() +
				' --file ' + environmentUrl();
		};
		const q2lspInstallCommand = () => {
			if (state.manager === 'pixi') {
				return 'cd .qiime2 && pixi run python -m pip install -U q2lsp';
			}
			if (state.manager === 'conda') {
				return 'conda run -n ' + environmentName() + ' python -m pip install -U q2lsp';
			}
			return inferredInterpreterPath() + ' -m pip install -U q2lsp';
		};

		const renderChips = () => {
			const chips = [];
			if (state.stepIndex === 0) {
				if (state.qiimeStatus !== 'ready') {
					chips.push({ kind: 'warning', label: 'QIIME 2 env not found' });
				}
				chips.push({ kind: 'neutral', label: 'Manager: ' + managerById[state.manager].label.replace(' / Miniforge', '') });
			} else {
				const manager = managerById[state.manager];
				if (state.qiimeStatus === 'ready' || state.stepIndex >= 3) {
					chips.push({ kind: 'success', label: 'QIIME 2 ready' });
				}
				chips.push({ kind: 'neutral', label: 'Distribution: ' + state.distribution });
				chips.push({ kind: 'neutral', label: 'Version: ' + state.version });
				chips.push({ kind: 'neutral', label: 'Manager: ' + manager.label.replace(' / Miniforge', '') });
				if (state.interpreterPath || state.stepIndex >= 3) {
					chips.push({ kind: 'neutral', label: 'Interpreter selected' });
				}
				if (state.q2lspStatus === 'ready') {
					chips.push({ kind: 'success', label: 'q2lsp ready' });
				}
				if (state.savedInterpreterPath) {
					chips.push({ kind: 'success', label: 'Path saved' });
				}
			}
			if (state.statusMessage) {
				chips.push({
					kind: state.statusMessage.includes('missing') || state.statusMessage.includes('not found') || state.statusMessage.includes('failed') ? 'warning' : 'neutral',
					label: state.statusMessage,
				});
			}
			document.getElementById('contextChips').innerHTML = chips
				.map((chip) => '<span class="chip ' + chip.kind + '">' + chip.label + '</span>')
				.join('');
		};

		const render = () => {
			updateSelectors();
			for (const screen of document.querySelectorAll('[data-screen]')) {
				screen.hidden = Number(screen.dataset.screen) !== state.stepIndex;
			}
			for (const step of document.querySelectorAll('[data-step-index]')) {
				const index = Number(step.dataset.stepIndex);
				step.classList.toggle('is-active', index === state.stepIndex);
				step.classList.toggle('is-complete', index < state.stepIndex);
			}
			for (const card of document.querySelectorAll('[data-manager]')) {
				card.classList.toggle('is-selected', card.dataset.manager === state.manager);
			}
			const manager = managerById[state.manager];
			document.getElementById('installManagerHeading').textContent =
				state.manager === 'manual' ? 'Manual setup' : 'Install ' + manager.label;
			document.getElementById('selectedManagerLabel').textContent = manager.label;
			document.getElementById('managerStatus').textContent =
				state.manager === 'manual'
					? 'External setup'
					: state.managerStatus === 'ready'
						? 'Installed'
						: state.managerStatus === 'missing'
							? 'Not installed'
							: 'Unknown';
			document.getElementById('managerCommand').textContent = manager.command;
			document.getElementById('installManagerPrimaryAction').textContent =
				state.manager === 'conda'
					? 'Open Miniforge Installer'
					: state.manager === 'pixi'
						? 'Install Pixi in Terminal'
						: 'Open QIIME 2 Quickstart';
			document.getElementById('qiimeManagerLabel').textContent = manager.label;
			document.getElementById('platformLabel').textContent = state.platform.label;
			document.getElementById('environmentName').textContent = environmentName();
			document.getElementById('environmentFile').textContent = environmentFile();
			document.getElementById('qiimeCommand').textContent = qiimeCommand();
			document.getElementById('q2lspCommand').textContent = q2lspInstallCommand();
			document.getElementById('managerStatusMessage').textContent =
				state.stepIndex === 1 ? state.statusMessage : '';
			document.getElementById('qiimeStatusMessage').textContent =
				state.stepIndex === 2 ? state.statusMessage : '';
			document.getElementById('q2lspStatusMessage').textContent =
				state.stepIndex === 3 ? state.statusMessage : '';
			document.getElementById('saveInterpreterPathAction').disabled = state.q2lspStatus !== 'ready';
			document.getElementById('restartServerAction').disabled = !state.savedInterpreterPath;
			document.querySelector('[data-progress="createEnvironment"]').className =
				'dot ' + (state.qiimeStatus === 'ready' ? 'success' : 'active');
			document.querySelector('[data-progress="qiimeInfo"]').className =
				'dot ' + (state.qiimeStatus === 'ready' ? 'success' : '');
			document.querySelector('[data-progress="locateInterpreter"]').className =
				'dot ' + (state.interpreterPath ? 'success' : '');
			document.querySelector('[data-progress="installQ2lsp"]').className =
				'dot ' + (state.q2lspStatus === 'ready' ? 'success' : 'active');
			document.querySelector('[data-progress="validateQ2lsp"]').className =
				'dot ' + (state.q2lspStatus === 'ready' ? 'success' : '');
			document.querySelector('[data-progress="saveInterpreter"]').className =
				'dot ' + (state.savedInterpreterPath ? 'success' : '');
			renderChips();
		};

		document.getElementById('distributionSelect').addEventListener('change', (event) => {
			state.distribution = event.target.value;
			render();
		});
		document.getElementById('versionSelect').addEventListener('change', (event) => {
			state.version = event.target.value;
			normalizeDistributionForVersion();
			render();
		});
		for (const card of document.querySelectorAll('[data-manager]')) {
			card.addEventListener('click', () => {
				state.manager = card.dataset.manager;
				render();
			});
		}
		for (const step of document.querySelectorAll('[data-step-index]')) {
			step.addEventListener('click', () => {
				state.stepIndex = Number(step.dataset.stepIndex);
				render();
			});
		}
		for (const button of document.querySelectorAll('[data-next]')) {
			button.addEventListener('click', () => {
				state.stepIndex = Math.min(3, state.stepIndex + 1);
				render();
			});
		}
		for (const button of document.querySelectorAll('[data-back]')) {
			button.addEventListener('click', () => {
				state.stepIndex = Math.max(0, state.stepIndex - 1);
				render();
			});
		}
		for (const button of document.querySelectorAll('[data-command]')) {
			button.addEventListener('click', () => {
				const command = button.dataset.command;
				const commandText = command === 'installManager'
					? managerById[state.manager].command
					: command === 'createQiimeEnvironment'
						? qiimeCommand()
						: command === 'installQ2lsp'
							? q2lspInstallCommand()
						: undefined;
				vscode.postMessage({
					command,
					commandText,
					interpreterPath: inferredInterpreterPath(),
					manager: state.manager,
					environmentName: environmentName(),
					environmentUrl: environmentUrl(),
					condaSubdir: state.platform.condaSubdir,
				});
			});
		}
		window.addEventListener('message', (event) => {
			if (event.data?.type === 'qiimeManifest') {
				state.environments = event.data.environments;
				state.statusMessage = event.data.message;
				normalizeDistributionForVersion();
				render();
				return;
			}
			if (event.data?.type !== 'wizardStatus') {
				return;
			}
			Object.assign(state, event.data.patch);
			if (event.data.patch.managerStatus === 'ready' && state.stepIndex === 1) {
				state.stepIndex = 2;
			}
			if (event.data.patch.qiimeStatus === 'ready' && state.stepIndex === 2) {
				state.stepIndex = 3;
			}
			render();
		});
		render();
	</script>
</body>
</html>`;
};

const handleSetupWizardMessage = async (params: {
	message: SetupWizardMessage;
	outputChannel?: vscode.OutputChannel;
	webview: vscode.Webview;
}): Promise<void> => {
	const command = toNonEmptyString(params.message.command);
	if (!command) {
		return;
	}

	switch (command) {
		case 'installManager':
			await confirmAndRunInTerminal(command, params.message.commandText);
			const managerCommand = toNonEmptyString(params.message.commandText);
			await postWizardStatus(params.webview, {
				message: managerCommand?.startsWith('Open ')
					? 'Opened setup documentation. When installation finishes, choose "I installed it, check again".'
					: 'Install command sent to terminal. When it finishes, choose "I installed it, check again".',
			});
			return;
		case 'createQiimeEnvironment':
			await createQiimeEnvironmentForWizard(params.webview, params.message);
			return;
		case 'installQ2lsp': {
			const manager = toNonEmptyString(params.message.manager);
			const interpreterResult = await resolveWizardInterpreter(params.message);
			if (!interpreterResult.ok) {
				await postWizardStatus(params.webview, {
					q2lspStatus: 'missing',
					message: interpreterResult.message,
				});
				return;
			}
			const installResult = await installQ2lspForWizard(manager, interpreterResult.interpreterPath);
			if (!installResult.ok) {
				await postWizardStatus(params.webview, {
					interpreterPath: interpreterResult.interpreterPath,
					q2lspStatus: 'missing',
					message: installResult.message,
				});
				return;
			}
			const validation = await validateInterpreter(
				execFileForValidation,
				interpreterResult.interpreterPath,
				VALIDATION_TIMEOUT_MS
			);
			await postWizardStatus(params.webview, {
				interpreterPath: interpreterResult.interpreterPath,
				q2lspStatus: validation.ok ? 'ready' : 'missing',
				message: validation.ok
					? 'q2lsp installed and validated.'
					: validation.missingModules?.length
						? `q2lsp install finished, but validation is still missing: ${validation.missingModules.join(', ')}.`
						: validation.errorMessage ?? 'q2lsp install finished, but validation failed.',
			});
			return;
		}
		case 'selectPythonInterpreter':
			await selectPythonInterpreter();
			return;
		case 'checkManager':
			await checkSelectedManager(params.webview, params.message.manager);
			return;
		case 'validateEnvironment':
			await validateQiimeEnvironment(params.webview, params.message);
			return;
		case 'validateQ2lsp':
			await validateQ2lsp(params.webview, params.message);
			return;
		case 'saveInterpreterPath':
			await saveInterpreterPath(params.webview, params.message);
			return;
		case 'restartServer':
			await vscode.commands.executeCommand('q2lsp.restartServer');
			await postWizardStatus(params.webview, {
				message: 'Restarted q2lsp server.',
			});
			return;
		default:
			return;
	}
};

const checkSelectedManager = async (webview: vscode.Webview, managerValue: unknown): Promise<void> => {
	const manager = toNonEmptyString(managerValue);
	if (manager === 'manual') {
		await postWizardStatus(webview, { managerStatus: 'ready', message: 'Manual setup selected.' });
		return;
	}

	const executable = manager === 'pixi' ? 'pixi' : 'conda';
	const result = await runExecutable(executable, ['--version']);
	if (result.ok) {
		await postWizardStatus(webview, {
			managerStatus: 'ready',
			message: `${executable} is available: ${formatStatusDetail(result.stdout)}`,
		});
		return;
	}

	await postWizardStatus(webview, {
		managerStatus: 'missing',
		message: `${executable} was not found. Install it, then check again.`,
	});
};

const createQiimeEnvironmentForWizard = async (
	webview: vscode.Webview,
	message: SetupWizardMessage
): Promise<void> => {
	const manager = toNonEmptyString(message.manager);
	const environmentName = toNonEmptyString(message.environmentName);
	const environmentUrl = toNonEmptyString(message.environmentUrl);
	if (manager === 'manual') {
		await vscode.env.openExternal(vscode.Uri.parse(QIIME_QUICKSTART_URL));
		await postWizardStatus(webview, {
			message: 'Opened QIIME 2 Quickstart. Return to validate your selected interpreter after setup.',
		});
		return;
	}
	if (!environmentName || !environmentUrl) {
		await postWizardStatus(webview, {
			qiimeStatus: 'missing',
			message: 'Could not resolve QIIME 2 environment metadata.',
		});
		return;
	}

	const selection = await vscode.window.showWarningMessage(
		`Create QIIME 2 environment ${environmentName} now? This can take a long time.`,
		{ modal: true },
		'Create Environment'
	);
	if (selection !== 'Create Environment') {
		await postWizardStatus(webview, {
			message: 'QIIME environment creation was cancelled.',
		});
		return;
	}

	const result = await vscode.window.withProgress(
		{
			location: vscode.ProgressLocation.Notification,
			title: `Creating ${environmentName}`,
			cancellable: false,
		},
		async () => {
			if (manager === 'pixi') {
				return createPixiQiimeEnvironment(environmentUrl);
			}
			return createCondaQiimeEnvironment(environmentName, environmentUrl, toNonEmptyString(message.condaSubdir));
		}
	);
	if (!result.ok) {
		await postWizardStatus(webview, {
			qiimeStatus: 'missing',
			message: result.message,
		});
		return;
	}

	const interpreterResult = await resolveWizardInterpreter(message);
	if (!interpreterResult.ok) {
		await postWizardStatus(webview, {
			qiimeStatus: 'missing',
			message: interpreterResult.message,
		});
		return;
	}

	const validation = await runPythonValidation(interpreterResult.interpreterPath, ['q2cli', 'qiime2']);
	await postWizardStatus(webview, {
		interpreterPath: interpreterResult.interpreterPath,
		qiimeStatus: validation.ok ? 'ready' : 'missing',
		message: validation.ok ? 'QIIME 2 environment created and validated.' : validation.message,
	});
};

const createCondaQiimeEnvironment = async (
	environmentName: string,
	environmentUrl: string,
	condaSubdir: string | undefined
): Promise<{ ok: true } | { ok: false; message: string }> => {
	const result = await runExecutable(
		'conda',
		['env', 'create', '--name', environmentName, '--file', environmentUrl],
		undefined,
		3600000,
		condaSubdir ? { CONDA_SUBDIR: condaSubdir } : undefined
	);
	return result.ok ? { ok: true } : { ok: false, message: result.message };
};

const createPixiQiimeEnvironment = async (
	environmentUrl: string
): Promise<{ ok: true } | { ok: false; message: string }> => {
	const pixiCwd = resolvePixiProjectCwd();
	if (!pixiCwd) {
		return { ok: false, message: 'Open a workspace before creating a Pixi QIIME 2 environment.' };
	}
	await mkdir(pixiCwd, { recursive: true });

	const initResult = await runExecutable(
		'pixi',
		['init', '--format', 'pyproject'],
		pixiCwd,
		600000
	);
	if (!initResult.ok && !initResult.message.includes('already')) {
		return { ok: false, message: initResult.message };
	}

	const importResult = await runExecutable(
		'pixi',
		['import', environmentUrl],
		pixiCwd,
		3600000
	);
	return importResult.ok ? { ok: true } : { ok: false, message: importResult.message };
};

const validateQiimeEnvironment = async (webview: vscode.Webview, message: SetupWizardMessage): Promise<void> => {
	const interpreterResult = await resolveWizardInterpreter(message);
	if (!interpreterResult.ok) {
		await postWizardStatus(webview, {
			qiimeStatus: 'missing',
			q2lspStatus: 'unknown',
			message: interpreterResult.message,
		});
		return;
	}
	const interpreterPath = interpreterResult.interpreterPath;

	const result = await runPythonValidation(interpreterPath, ['q2cli', 'qiime2']);
	if (result.ok) {
		await postWizardStatus(webview, {
			interpreterPath,
			qiimeStatus: 'ready',
			message: 'QIIME 2 validation passed.',
		});
		return;
	}

	await postWizardStatus(webview, {
		interpreterPath,
		qiimeStatus: 'missing',
		message: result.message,
	});
};

const validateQ2lsp = async (webview: vscode.Webview, message: SetupWizardMessage): Promise<void> => {
	const interpreterResult = await resolveWizardInterpreter(message);
	if (!interpreterResult.ok) {
		await postWizardStatus(webview, {
			q2lspStatus: 'missing',
			message: interpreterResult.message,
		});
		return;
	}
	const interpreterPath = interpreterResult.interpreterPath;

	const result = await validateInterpreter(execFileForValidation, interpreterPath, VALIDATION_TIMEOUT_MS);
	if (result.ok) {
		await postWizardStatus(webview, {
			interpreterPath,
			qiimeStatus: 'ready',
			q2lspStatus: 'ready',
			message: 'q2lsp validation passed.',
		});
		return;
	}

	await postWizardStatus(webview, {
		interpreterPath,
		q2lspStatus: 'missing',
		message: result.missingModules?.length
			? `Missing modules: ${result.missingModules.join(', ')}.`
			: result.errorMessage ?? 'q2lsp validation failed.',
	});
};

const saveInterpreterPath = async (webview: vscode.Webview, message: SetupWizardMessage): Promise<void> => {
	const interpreterResult = await resolveWizardInterpreter(message);
	if (!interpreterResult.ok) {
		await postWizardStatus(webview, {
			message: interpreterResult.message,
		});
		return;
	}
	const interpreterPath = interpreterResult.interpreterPath;

	const scope = await vscode.window.showQuickPick(
		[
			{
				label: 'Workspace',
				description: 'Recommended for project-specific QIIME 2 environments',
				target: vscode.ConfigurationTarget.Workspace,
			},
			{
				label: 'User',
				description: 'Use this interpreter for all workspaces',
				target: vscode.ConfigurationTarget.Global,
			},
		],
		{
			placeHolder: 'Where should q2lsp.interpreterPath be saved?',
		}
	);
	if (!scope) {
		await postWizardStatus(webview, {
			message: 'Saving q2lsp.interpreterPath was cancelled.',
		});
		return;
	}

	await vscode.workspace.getConfiguration('q2lsp').update(
		'interpreterPath',
		interpreterPath,
		scope.target
	);
	await postWizardStatus(webview, {
		interpreterPath,
		savedInterpreterPath: true,
		message: `Saved q2lsp.interpreterPath to ${scope.label.toLowerCase()} settings.`,
	});
};

const resolveWizardInterpreter = async (
	message: SetupWizardMessage
): Promise<{ ok: true; interpreterPath: string } | { ok: false; message: string }> => {
	const manager = toNonEmptyString(message.manager);
	const environmentName = toNonEmptyString(message.environmentName);
	const explicitInterpreterPath = toNonEmptyString(message.interpreterPath);

	if (manager === 'conda' && environmentName) {
		const result = await runExecutable('conda', [
			'run',
			'-n',
			environmentName,
			'python',
			'-c',
			'import sys; print(sys.executable)',
		]);
		if (result.ok) {
			return { ok: true, interpreterPath: result.stdout.trim() };
		}
		return { ok: false, message: `Could not resolve Conda environment ${environmentName}: ${result.message}` };
	}

	if (manager === 'pixi') {
		const result = await runExecutable(
			'pixi',
			['run', 'python', '-c', 'import sys; print(sys.executable)'],
			resolvePixiProjectCwd()
		);
		if (result.ok) {
			return { ok: true, interpreterPath: result.stdout.trim() };
		}
		return { ok: false, message: `Could not resolve Pixi Python interpreter: ${result.message}` };
	}

	if (explicitInterpreterPath) {
		return { ok: true, interpreterPath: explicitInterpreterPath };
	}

	return { ok: false, message: 'Select or create a QIIME 2 Python interpreter before continuing.' };
};

const installQ2lspForWizard = async (
	manager: string | undefined,
	interpreterPath: string
): Promise<{ ok: true } | { ok: false; message: string }> => {
	const selection = await vscode.window.showWarningMessage(
		'Install q2lsp into the selected QIIME 2 environment now?',
		{ modal: true },
		'Install q2lsp'
	);
	if (selection !== 'Install q2lsp') {
		return { ok: false, message: 'q2lsp install was cancelled.' };
	}

	return vscode.window.withProgress(
		{
			location: vscode.ProgressLocation.Notification,
			title: 'Installing q2lsp',
			cancellable: false,
		},
		async () => {
			if (manager === 'pixi') {
				const result = await runExecutable(
					'pixi',
					['run', 'python', '-m', 'pip', 'install', '-U', 'q2lsp'],
					resolvePixiProjectCwd(),
					600000
				);
				return result.ok ? { ok: true } : { ok: false, message: result.message };
			}

			const result = await runExecutable(
				interpreterPath,
				['-m', 'pip', 'install', '-U', 'q2lsp'],
				undefined,
				600000
			);
			return result.ok ? { ok: true } : { ok: false, message: result.message };
		}
	);
};

const refreshQiimeManifest = async (webview: vscode.Webview, platform: QiimePlatform): Promise<void> => {
	const fallbackEnvironments = buildFallbackQiimeEnvironments(platform);
	const remoteEnvironments = await fetchQiimeEnvironments(platform);
	if (remoteEnvironments.length > 0) {
		const mergedEnvironments = mergeQiimeEnvironments(fallbackEnvironments, remoteEnvironments);
		await webview.postMessage({
			type: 'qiimeManifest',
			environments: mergedEnvironments,
			message: remoteEnvironments.length < fallbackEnvironments.length
				? 'Merged partial online QIIME 2 version data with bundled versions.'
				: 'Refreshed QIIME 2 versions from qiime2/distributions.',
		});
		return;
	}

	await webview.postMessage({
		type: 'qiimeManifest',
		environments: fallbackEnvironments,
		message: 'Could not refresh QIIME 2 versions. Using bundled version list.',
	});
};

const fetchQiimeEnvironments = async (platform: QiimePlatform): Promise<QiimeEnvironmentOption[]> => {
	try {
		const packageIndexEnvironments = await fetchQiimeEnvironmentsFromPackageIndex(platform);
		const exactGithubEnvironments = await fetchQiimeEnvironmentsFromGitHubContents(platform);
		const environments = mergeQiimeEnvironments(packageIndexEnvironments, exactGithubEnvironments)
			.sort(compareQiimeEnvironmentOptions);
		if (environments.length > 0) {
			return environments;
		}
		return await fetchQiimeEnvironmentsFromRecursiveTree(platform);
	} catch {
		return [];
	}
};

const fetchQiimeEnvironmentsFromPackageIndex = async (
	platform: QiimePlatform
): Promise<QiimeEnvironmentOption[]> => {
	const versionIndex = await fetchDirectoryIndex(QIIME_PACKAGES_BASE_URL);
	const versions = versionIndex
		.filter((entry) => /^\d{4}\.\d+$/.test(entry))
		.sort((left, right) => right.localeCompare(left, undefined, { numeric: true }));
	const environments: QiimeEnvironmentOption[] = [];

	for (const version of versions) {
		const distributionIndex = await fetchDirectoryIndex(`${QIIME_PACKAGES_BASE_URL}/${version}`);
		const distributions = distributionIndex
			.filter((entry) => !entry.startsWith('.'))
			.filter((entry) => !/^\d{4}\.\d+$/.test(entry));
		for (const distribution of distributions) {
			const releasedIndex = await fetchDirectoryIndex(`${QIIME_PACKAGES_BASE_URL}/${version}/${distribution}`);
			if (!releasedIndex.includes('released')) {
				continue;
			}
			const environment = buildSyntheticQiimeEnvironment(version, distribution, platform);
			if (environment) {
				environments.push(environment);
			}
		}
	}

	return environments;
};

const fetchDirectoryIndex = async (url: string): Promise<string[]> => {
	const response = await fetch(`${url.replace(/\/$/, '')}/`);
	if (!response.ok) {
		return [];
	}
	const html = await response.text();
	const entries: string[] = [];
	for (const match of html.matchAll(/href=["']([^"']+)["']/gi)) {
		const href = match[1];
		if (!href || href.startsWith('?') || href.startsWith('#') || href.startsWith('../')) {
			continue;
		}
		const trimmed = href.replace(/\/$/, '');
		const decoded = decodeURIComponent(trimmed.split('/').filter(Boolean).pop() ?? '');
		if (decoded && decoded !== '..') {
			entries.push(decoded);
		}
	}
	return Array.from(new Set(entries));
};

export const buildSyntheticQiimeEnvironment = (
	version: string,
	distribution: string,
	platform: QiimePlatform
): QiimeEnvironmentOption | undefined => {
	if (isRachisQiimeVersion(version)) {
		const fileName = `rachis-${distribution}-${platform.id}-conda.yml`;
		return {
			version,
			distribution,
			platform: platform.id,
			fileName,
			url: `https://raw.githubusercontent.com/qiime2/distributions/refs/heads/dev/${version}/${distribution}/released/${fileName}`,
			environmentName: fileName.replace(/-(linux-64|osx-64|osx-arm64|linux|osx)-conda\.yml$/, ''),
		};
	}

	if (distribution === 'qiime2') {
		return undefined;
	}
	const legacyPlatform = platform.id === 'linux-64' ? 'linux' : 'osx';
	const fileName = `qiime2-${distribution}-${version}-py310-${legacyPlatform}-conda.yml`;
	return {
		version,
		distribution,
		platform: platform.id,
		fileName,
		url: `https://raw.githubusercontent.com/qiime2/distributions/refs/heads/dev/${version}/${distribution}/released/${fileName}`,
		environmentName: `qiime2-${distribution}-${version}`,
	};
};

type GitHubContentEntry = {
	name?: unknown;
	path?: unknown;
	type?: unknown;
};

const fetchQiimeEnvironmentPaths = async (): Promise<string[]> => {
	const epochEntries = await fetchGitHubContents('');
	const epochPaths = epochEntries
		.filter((entry) => entry.type === 'dir' && typeof entry.name === 'string' && /^\d{4}\.\d+$/.test(entry.name))
		.map((entry) => entry.name as string)
		.sort((left, right) => right.localeCompare(left, undefined, { numeric: true }));
	const environmentPaths: string[] = [];

	for (const epoch of epochPaths) {
		const distributionEntries = await fetchGitHubContents(epoch);
		const distributions = distributionEntries
			.filter((entry) => entry.type === 'dir' && typeof entry.name === 'string')
			.map((entry) => entry.name as string);
		for (const distribution of distributions) {
			const releasedEntries = await fetchGitHubContents(`${epoch}/${distribution}/released`);
			for (const entry of releasedEntries) {
				if (entry.type === 'file' && typeof entry.path === 'string' && entry.path.endsWith('-conda.yml')) {
					environmentPaths.push(entry.path);
				}
			}
		}
	}

	return environmentPaths;
};

const fetchQiimeEnvironmentsFromGitHubContents = async (
	platform: QiimePlatform
): Promise<QiimeEnvironmentOption[]> => {
	const paths = await fetchQiimeEnvironmentPaths();
	return paths
		.map((entryPath) => parseQiimeEnvironmentPath(entryPath))
		.filter((environment): environment is QiimeEnvironmentOption => environment !== undefined)
		.filter((environment) => environment.platform === platform.id)
		.sort(compareQiimeEnvironmentOptions);
};

const fetchGitHubContents = async (path: string): Promise<GitHubContentEntry[]> => {
	const suffix = path ? `/${path}` : '';
	const response = await fetch(`${QIIME_MANIFEST_CONTENTS_URL}${suffix}?ref=dev`, {
		headers: {
			Accept: 'application/vnd.github+json',
		},
	});
	if (!response.ok) {
		return [];
	}
	const parsed = (await response.json()) as unknown;
	return Array.isArray(parsed) ? parsed as GitHubContentEntry[] : [];
};

const fetchQiimeEnvironmentsFromRecursiveTree = async (
	platform: QiimePlatform
): Promise<QiimeEnvironmentOption[]> => {
	const response = await fetch(QIIME_MANIFEST_TREE_URL, {
		headers: {
			Accept: 'application/vnd.github+json',
		},
	});
	if (!response.ok) {
		return [];
	}
	const parsed = (await response.json()) as {
		tree?: Array<{ path?: unknown; type?: unknown }>;
	};
	const paths = parsed.tree
		?.filter((entry) => entry.type === 'blob' && typeof entry.path === 'string')
		.map((entry) => entry.path as string) ?? [];
	return paths
		.map((entryPath) => parseQiimeEnvironmentPath(entryPath))
		.filter((environment): environment is QiimeEnvironmentOption => environment !== undefined)
		.filter((environment) => environment.platform === platform.id)
		.sort(compareQiimeEnvironmentOptions);
};

export const parseQiimeEnvironmentPath = (entryPath: string): QiimeEnvironmentOption | undefined => {
	const match = /^(?<version>\d{4}\.\d+)\/(?<distribution>[^/]+)\/released\/(?<fileName>.+-(?<platform>linux-64|osx-64|osx-arm64|linux|osx)-conda\.yml)$/.exec(entryPath);
	const groups = match?.groups;
	if (!groups) {
		return undefined;
	}
	const platform = normalizeQiimePlatformId(groups.platform);
	const fileMetadata = parseQiimeEnvironmentFileName(groups.fileName);
	if (!fileMetadata) {
		return undefined;
	}
	if (fileMetadata.platform !== platform || fileMetadata.distribution !== groups.distribution) {
		return undefined;
	}
	if (fileMetadata.kind === 'rachis' && !isRachisQiimeVersion(groups.version)) {
		return undefined;
	}
	if (fileMetadata.kind === 'legacy') {
		if (isRachisQiimeVersion(groups.version) || fileMetadata.version !== groups.version) {
			return undefined;
		}
	}

	return {
		version: groups.version,
		distribution: groups.distribution,
		platform,
		fileName: groups.fileName,
		url: `https://raw.githubusercontent.com/qiime2/distributions/refs/heads/dev/${entryPath}`,
		environmentName: groups.fileName.replace(/-(linux-64|osx-64|osx-arm64|linux|osx)-conda\.yml$/, ''),
	};
};

type QiimeEnvironmentFileMetadata =
	| {
		kind: 'rachis';
		distribution: string;
		platform: string;
	}
	| {
		kind: 'legacy';
		distribution: string;
		version: string;
		platform: string;
	};

const parseQiimeEnvironmentFileName = (fileName: string): QiimeEnvironmentFileMetadata | undefined => {
	const rachisMatch = /^rachis-(?<distribution>.+)-(?<platform>linux-64|osx-64|osx-arm64)-conda\.yml$/.exec(fileName);
	if (rachisMatch?.groups) {
		return {
			kind: 'rachis',
			distribution: rachisMatch.groups.distribution,
			platform: normalizeQiimePlatformId(rachisMatch.groups.platform),
		};
	}

	const legacyMatch = /^qiime2-(?<distribution>.+)-(?<version>\d{4}\.\d+)-py\d+-(?<platform>linux|osx)-conda\.yml$/.exec(fileName);
	if (!legacyMatch?.groups) {
		return undefined;
	}
	return {
		kind: 'legacy',
		distribution: legacyMatch.groups.distribution,
		version: legacyMatch.groups.version,
		platform: normalizeQiimePlatformId(legacyMatch.groups.platform),
	};
};

const isRachisQiimeVersion = (version: string): boolean => {
	const year = Number(version.split('.')[0]);
	return Number.isFinite(year) && year >= 2026;
};

const normalizeQiimePlatformId = (platform: string): string => {
	if (platform === 'linux') {
		return 'linux-64';
	}
	if (platform === 'osx') {
		return 'osx-64';
	}
	return platform;
};

const compareQiimeEnvironmentOptions = (
	left: QiimeEnvironmentOption,
	right: QiimeEnvironmentOption
): number => {
	const versionComparison = right.version.localeCompare(left.version, undefined, { numeric: true });
	if (versionComparison !== 0) {
		return versionComparison;
	}
	return left.distribution.localeCompare(right.distribution);
};

export const resolveQiimePlatform = (platform: NodeJS.Platform, arch: string): QiimePlatform => {
	if (platform === 'darwin') {
		if (arch === 'arm64') {
			return { id: 'osx-64', label: 'macOS Apple Silicon using osx-64', condaSubdir: 'osx-64' };
		}
		return { id: 'osx-64', label: 'macOS Intel' };
	}
	return { id: 'linux-64', label: 'Linux / WSL' };
};

export const buildFallbackQiimeEnvironments = (platform: QiimePlatform): QiimeEnvironmentOption[] => {
	const options: QiimeEnvironmentOption[] = [];
	for (const version of QIIME_VERSIONS) {
		if (version.startsWith('2026.')) {
			const fileName = `rachis-qiime2-${platform.id}-conda.yml`;
			options.push({
				version,
				distribution: 'qiime2',
				platform: platform.id,
				fileName,
				url: `https://raw.githubusercontent.com/qiime2/distributions/refs/heads/dev/${version}/qiime2/released/${fileName}`,
				environmentName: fileName.replace(/-(linux-64|osx-64|osx-arm64|linux|osx)-conda\.yml$/, ''),
			});
			continue;
		}

		for (const distribution of QIIME_DISTRIBUTIONS) {
			const legacyPlatform = platform.id === 'linux-64' ? 'linux' : 'osx';
			const fileName = `qiime2-${distribution}-${version}-py310-${legacyPlatform}-conda.yml`;
			options.push({
				version,
				distribution,
				platform: platform.id,
				fileName,
				url: `https://raw.githubusercontent.com/qiime2/distributions/refs/heads/dev/${version}/${distribution}/released/${fileName}`,
				environmentName: `qiime2-${distribution}-${version}`,
			});
		}
	}
	return options;
};

const uniqueQiimeDistributions = (environments: QiimeEnvironmentOption[]): string[] => {
	return Array.from(new Set(environments.map((environment) => environment.distribution))).sort();
};

const uniqueQiimeVersions = (environments: QiimeEnvironmentOption[]): string[] => {
	return Array.from(new Set(environments.map((environment) => environment.version)))
		.sort((left, right) => right.localeCompare(left, undefined, { numeric: true }));
};

const resolveInitialQiimeVersion = (environments: QiimeEnvironmentOption[]): string => {
	return uniqueQiimeVersions(environments)[0] ?? QIIME_VERSIONS[0];
};

export const mergeQiimeEnvironments = (
	fallbackEnvironments: QiimeEnvironmentOption[],
	remoteEnvironments: QiimeEnvironmentOption[]
): QiimeEnvironmentOption[] => {
	const remoteVersionPlatforms = new Set(
		remoteEnvironments.map((environment) => formatQiimeVersionPlatformKey(environment))
	);
	const merged = new Map<string, QiimeEnvironmentOption>();
	for (const environment of fallbackEnvironments) {
		if (remoteVersionPlatforms.has(formatQiimeVersionPlatformKey(environment))) {
			continue;
		}
		merged.set(formatQiimeEnvironmentKey(environment), environment);
	}
	for (const environment of remoteEnvironments) {
		merged.set(formatQiimeEnvironmentKey(environment), environment);
	}
	return Array.from(merged.values()).sort(compareQiimeEnvironmentOptions);
};

const formatQiimeVersionPlatformKey = (environment: QiimeEnvironmentOption): string => {
	return [
		environment.version,
		environment.platform,
	].join('\0');
};

const formatQiimeEnvironmentKey = (environment: QiimeEnvironmentOption): string => {
	return [
		environment.version,
		environment.distribution,
		environment.platform,
	].join('\0');
};

const postWizardStatus = async (
	webview: vscode.Webview,
	patch: Record<string, string | boolean>
): Promise<void> => {
	await webview.postMessage({
		type: 'wizardStatus',
		patch,
	});
};

const runPythonValidation = async (
	interpreterPath: string,
	modules: readonly string[]
): Promise<{ ok: true } | { ok: false; message: string }> => {
	const result = await runExecutable(interpreterPath, ['-c', buildInterpreterValidationSnippet(modules)]);
	if (!result.ok) {
		return { ok: false, message: result.message };
	}

	const details = parseInterpreterValidationStdout(result.stdout);
	if (!details) {
		return { ok: false, message: 'Unexpected Python validation output.' };
	}
	if (details.missing.length > 0) {
		return { ok: false, message: `Missing modules: ${details.missing.join(', ')}.` };
	}
	return { ok: true };
};

const runExecutable = async (
	file: string,
	args: readonly string[],
	cwd?: string,
	timeoutMs: number = VALIDATION_TIMEOUT_MS,
	envOverrides?: NodeJS.ProcessEnv
): Promise<{ ok: true; stdout: string } | { ok: false; message: string }> => {
	return new Promise((resolve) => {
		const execOptions: ExecFileOptionsWithStringEncoding = {
			encoding: 'utf8',
			timeout: timeoutMs,
			env: envOverrides ? { ...process.env, ...envOverrides } : process.env,
			...(cwd ? { cwd } : {}),
		};
		execFile(file, args, execOptions, (error, stdout, stderr) => {
			if (error) {
				resolve({
					ok: false,
					message: formatStatusDetail(stderr) || error.message,
				});
				return;
			}
			resolve({ ok: true, stdout });
		});
	});
};

const resolvePixiProjectCwd = (): string | undefined => {
	const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
	if (!workspaceFolder || workspaceFolder.uri.scheme !== 'file') {
		return undefined;
	}
	return vscode.Uri.joinPath(workspaceFolder.uri, '.qiime2').fsPath;
};

const formatStatusDetail = (value: string | undefined): string => {
	const trimmed = value?.trim();
	if (!trimmed) {
		return '';
	}
	return trimmed.length > 160 ? `${trimmed.slice(0, 160)}...` : trimmed;
};

const confirmAndRunInTerminal = async (action: string, commandText: unknown): Promise<void> => {
	const command = toNonEmptyString(commandText);
	if (!command || command.startsWith('Open ')) {
		if (command?.includes('Miniforge')) {
			await vscode.env.openExternal(vscode.Uri.parse(MINIFORGE_INSTALL_URL));
			return;
		}
		if (command?.includes('QIIME 2 Quickstart')) {
			await vscode.env.openExternal(vscode.Uri.parse(QIIME_QUICKSTART_URL));
			return;
		}
		vscode.window.showInformationMessage(command ?? 'Follow the manual setup instructions, then return to the wizard.');
		return;
	}

	const selection = await vscode.window.showWarningMessage(
		`Run ${action} command in a VS Code terminal?`,
		{ modal: true },
		'Run in Terminal'
	);
	if (selection !== 'Run in Terminal') {
		return;
	}

	const terminal = vscode.window.createTerminal({ name: 'q2lsp Setup Wizard' });
	terminal.show(true);
	terminal.sendText(command);
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
