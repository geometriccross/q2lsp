import {
	type QiimeEnvironmentOption,
	type QiimePlatform,
} from './qiimeConstants';
import { resolveQiimePlatform } from './qiimeMetadata';

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

type SetupWizardOptions = {
	nonce: string;
	interpreterPath?: string;
	platform?: QiimePlatform;
	environments?: QiimeEnvironmentOption[];
};

export const buildSetupWizardHtml = (options: SetupWizardOptions): string => {
	const initialInterpreterPath = options.interpreterPath ?? '';
	const platform = options.platform ?? resolveQiimePlatform(process.platform, process.arch);
	const environments = options.environments ?? [];
	const stepButtons = SETUP_WIZARD_FLOW_STEPS.map(
		(step, index) => `
			<div class="step" data-step-index="${index}">
				<span class="step-index">${index + 1}</span>
				<span>${escapeHtml(step.label.replace(/^\d\s/, ''))}</span>
			</div>`
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
		(environment) => environment.version === initialVersion
	));
	const initialEnvironmentOptions = environments
		.filter((environment) => environment.version === initialVersion)
		.filter((environment) => environment.distribution === (initialDistributions[0] ?? ''))
		.sort((left, right) => left.fileName.localeCompare(right.fileName));
	const distributionOptions = initialDistributions.map(
		(distribution) => `<option value="${escapeHtml(distribution)}">${escapeHtml(distribution)}</option>`
	).join('');
	const environmentUrlOptions = initialEnvironmentOptions.map(
		(environment) => `<option value="${escapeHtml(environment.url)}">${escapeHtml(environment.fileName)}</option>`
	).join('');
	const initialVersions = uniqueQiimeVersions(environments);
	const versionOptions = initialVersions.map((version) => `<option value="${version}">${escapeHtml(version)}</option>`).join('');

	const bootstrapState = JSON.stringify({
		interpreterPath: initialInterpreterPath,
		managers: SETUP_WIZARD_MANAGERS,
		platform,
		environments,
		initialVersion,
		initialDistribution: initialDistributions[0] ?? '',
		initialEnvironmentUrl: initialEnvironmentOptions[0]?.url ?? '',
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
		.field-row.single {
			grid-template-columns: minmax(0, 1fr);
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
		.action[data-back] {
			margin-right: auto;
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
						Version
						<select id="versionSelect">
							${versionOptions}
						</select>
					</label>
					<label>
						Distribution
						<select id="distributionSelect">
							${distributionOptions}
						</select>
					</label>
				</div>
				<div class="field-row single">
					<label>
						Environment file URL
						<select id="environmentUrlSelect">
							${environmentUrlOptions}
						</select>
					</label>
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
			environmentUrl: bootstrap.initialEnvironmentUrl,
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
			.filter((environment) => environment.version === state.version);
		const firstEnvironmentForVersion = () => availableEnvironmentsForVersion()
			.sort((left, right) => left.distribution.localeCompare(right.distribution))[0];
		const availableEnvironmentsForDistribution = () => availableEnvironmentsForVersion()
			.filter((environment) => environment.distribution === state.distribution);
		const firstEnvironmentForDistribution = () => availableEnvironmentsForDistribution()
			.sort((left, right) => left.url.localeCompare(right.url))[0];
		const normalizeDistributionForVersion = () => {
			const distributionsForVersion = new Set(availableEnvironmentsForVersion()
				.map((environment) => environment.distribution));
			if (!distributionsForVersion.has(state.distribution)) {
				state.distribution = firstEnvironmentForVersion()?.distribution || '';
			}
		};
		const normalizeEnvironmentUrlForDistribution = () => {
			const urlsForDistribution = new Set(availableEnvironmentsForDistribution()
				.map((environment) => environment.url));
			if (!urlsForDistribution.has(state.environmentUrl)) {
				state.environmentUrl = firstEnvironmentForDistribution()?.url || '';
			}
		};
		const updateSelectors = () => {
			const availableVersions = uniqueValues(state.environments
				.map((environment) => environment.version));
			const versionSelect = document.getElementById('versionSelect');
			versionSelect.innerHTML = availableVersions
				.map((version) => '<option value="' + version + '">' + version + '</option>')
				.join('');
			if (!availableVersions.includes(state.version)) {
				state.version = availableVersions[0] || '';
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
			normalizeEnvironmentUrlForDistribution();

			const environmentUrlSelect = document.getElementById('environmentUrlSelect');
			environmentUrlSelect.innerHTML = availableEnvironmentsForDistribution()
				.sort((left, right) => left.fileName.localeCompare(right.fileName))
				.map((environment) => '<option value="' + environment.url + '">' + environment.fileName + '</option>')
				.join('');
			normalizeEnvironmentUrlForDistribution();
			environmentUrlSelect.value = state.environmentUrl;
		};

		const selectedEnvironment = () => state.environments.find((environment) =>
			environment.distribution === state.distribution &&
			environment.version === state.version &&
			environment.url === state.environmentUrl
		) || firstEnvironmentForDistribution() || firstEnvironmentForVersion();
		const environmentName = () => selectedEnvironment()?.environmentName || '';
		const environmentUrl = () => selectedEnvironment()?.url || '';
		const inferredInterpreterPath = () => state.interpreterPath ||
			'/opt/miniforge/envs/' + environmentName() + '/bin/python';
		const qiimeCommand = () => {
			if (state.manager === 'pixi') {
				return 'pixi init && pixi import ' + environmentUrl() + ' && pixi install';
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
				return 'pixi run python -m pip install -U q2lsp';
			}
			if (state.manager === 'conda') {
				return 'conda run -n ' + environmentName() + ' python -m pip install -U q2lsp';
			}
			return inferredInterpreterPath() + ' -m pip install -U q2lsp';
		};

		const renderChips = () => {
			const chips = [];
			chips.push({ kind: 'neutral', label: 'OS: ' + state.platform.label });
			if (state.stepIndex >= 1) {
				chips.push({
					kind: 'neutral',
					label: 'Manager: ' + managerById[state.manager].label.replace(' / Miniforge', ''),
				});
			}
			if (state.stepIndex >= 2) {
				chips.push({ kind: 'neutral', label: 'Distribution: ' + state.distribution });
				chips.push({ kind: 'neutral', label: 'Version: ' + state.version });
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
			normalizeEnvironmentUrlForDistribution();
			render();
		});
		document.getElementById('environmentUrlSelect').addEventListener('change', (event) => {
			state.environmentUrl = event.target.value;
			render();
		});
		document.getElementById('versionSelect').addEventListener('change', (event) => {
			state.version = event.target.value;
			normalizeDistributionForVersion();
			normalizeEnvironmentUrlForDistribution();
			render();
		});
		for (const card of document.querySelectorAll('[data-manager]')) {
			card.addEventListener('click', () => {
				state.manager = card.dataset.manager;
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
				normalizeEnvironmentUrlForDistribution();
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


const uniqueQiimeDistributions = (environments: QiimeEnvironmentOption[]): string[] => {
	return Array.from(new Set(environments.map((environment) => environment.distribution))).sort();
};

const uniqueQiimeVersions = (environments: QiimeEnvironmentOption[]): string[] => {
	return Array.from(new Set(environments.map((environment) => environment.version)))
		.sort((left, right) => right.localeCompare(left, undefined, { numeric: true }));
};

const resolveInitialQiimeVersion = (environments: QiimeEnvironmentOption[]): string => {
	return uniqueQiimeVersions(environments)[0] ?? '';
};

const escapeHtml = (value: string): string => {
	return value
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&#39;');
};
