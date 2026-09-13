import {
	type QiimeEnvironmentOption,
	type QiimePlatform,
} from './qiimeConstants';
import { resolveQiimePlatform } from './qiimeMetadata';

export const SETUP_WIZARD_EXISTING_ROUTE_STEPS = [
	{ id: 'selectInterpreter', label: 'Select Python interpreter' },
	{ id: 'validateQiime', label: 'Validate QIIME 2' },
	{ id: 'installOrValidateQ2lsp', label: 'Install or validate q2lsp' },
	{ id: 'saveInterpreterPath', label: 'Save interpreter path' },
	{ id: 'complete', label: 'Setup complete' },
] as const;

export const SETUP_WIZARD_NEW_ROUTE_STEPS = [
	{ id: 'chooseManager', label: 'Choose manager' },
	{ id: 'validateManager', label: 'Validate manager' },
	{ id: 'chooseTarget', label: 'Choose QIIME 2 target' },
	{ id: 'createEnvironment', label: 'Create environment in Terminal' },
	{ id: 'validateQiime', label: 'Validate QIIME 2' },
	{ id: 'installOrValidateQ2lsp', label: 'Install or validate q2lsp' },
	{ id: 'saveInterpreterPath', label: 'Save interpreter path' },
	{ id: 'complete', label: 'Setup complete' },
] as const;

export const SETUP_WIZARD_FLOW_STEPS = SETUP_WIZARD_NEW_ROUTE_STEPS;

const minicondaInstallerPlatform = process.platform === 'darwin' ? 'MacOSX' : 'Linux';
const MINICONDA_INSTALL_COMMAND =
	`curl -fsSLo Miniconda3.sh "https://repo.anaconda.com/miniconda/Miniconda3-latest-${minicondaInstallerPlatform}-$(uname -m).sh" && bash Miniconda3.sh`;

export const SETUP_WIZARD_MANAGERS = [
	{
		id: 'conda',
		label: 'Conda / Miniconda',
		description: 'Recommended default for QIIME 2 environments',
		command: MINICONDA_INSTALL_COMMAND,
	},
	{
		id: 'pixi',
		label: 'Pixi',
		description: 'Advanced project-local setup',
		command: 'curl -fsSL https://pixi.sh/install.sh | sh',
	},
	{
		id: 'manual',
		label: 'Manual',
		description: 'Custom setup escape hatch',
		command: 'Open QIIME 2 Quickstart',
	},
] as const;

export type SetupWizardRoute = 'start' | 'existing' | 'new';
export type SetupWizardCandidateSource = 'config' | 'pythonExtension' | 'path' | 'manual';

export type SetupWizardInterpreterCandidate = {
	id: string;
	label: string;
	path: string;
	source: SetupWizardCandidateSource;
};


export type SetupWizardTargetIdentity = {
	route?: unknown;
	interpreterPath?: unknown;
	manager?: unknown;
	version?: unknown;
	distribution?: unknown;
	environmentName?: unknown;
	environmentUrl?: unknown;
};

export type SetupWizardSaveState = SetupWizardTargetIdentity & {
	qiimeStatus?: unknown;
	q2lspStatus?: unknown;
	validatedInterpreterPath?: unknown;
	validatedTargetKey?: unknown;
	targetKey?: unknown;
};

export type WizardStepStatus = 'passed' | 'failed' | 'current' | 'not started';

export type WizardState = {
	route: SetupWizardRoute;
	manager: string;
	managerStatus: string;
	managerStatuses: Record<string, string>;
	qiimeStatus: string;
	q2lspStatus: string;
	q2lspVersion: string;
	pendingCommand: string;
	statusMessage: string;
	selectedCandidateId: string;
	interpreterPath: string;
	candidates: SetupWizardInterpreterCandidate[];
	environments: QiimeEnvironmentOption[];
	metadataStatus: 'loading' | 'ready' | 'missing';
	version: string;
	distribution: string;
	environmentUrl: string;
	platform: QiimePlatform;
	submittedTarget?: { version: string; distribution: string; environmentName: string; environmentUrl: string };
	savedInterpreterPath: boolean;
	validatedInterpreterPath?: string;
	validatedTargetKey?: string;
};

const normalizeIdentityPart = (value: unknown): string => typeof value === 'string' ? value.trim() : '';

export const buildWizardTargetKey = (target: SetupWizardTargetIdentity): string => {
	const route = normalizeIdentityPart(target.route);
	if (route === 'existing') {
		return `existing:${normalizeIdentityPart(target.interpreterPath)}`;
	}
	if (route === 'new') {
		return [
			'new',
			normalizeIdentityPart(target.manager),
			normalizeIdentityPart(target.version),
			normalizeIdentityPart(target.distribution),
			normalizeIdentityPart(target.environmentName),
			normalizeIdentityPart(target.environmentUrl),
		].join(':');
	}
	return `${route}:`;
};


type SetupWizardOptions = {
	nonce: string;
	interpreterPath?: string;
	activePythonInterpreterPath?: string;
	interpreterCandidates?: SetupWizardInterpreterCandidate[];
	platform?: QiimePlatform;
	environments?: QiimeEnvironmentOption[];
	metadataStatus?: 'loading' | 'ready' | 'missing';
};

export const buildSetupWizardInterpreterCandidates = (params: {
	configuredInterpreterPath?: string;
	activePythonInterpreterPath?: string;
	pathCandidates?: readonly string[];
}): SetupWizardInterpreterCandidate[] => {
	const candidates: SetupWizardInterpreterCandidate[] = [];
	const seen = new Set<string>();
	const add = (candidate: SetupWizardInterpreterCandidate): void => {
		const key = candidate.path.trim();
		if (!key || seen.has(key)) {
			return;
		}
		seen.add(key);
		candidates.push({ ...candidate, path: key });
	};

	add({
		id: 'configured',
		label: 'Configured q2lsp interpreter',
		path: params.configuredInterpreterPath ?? '',
		source: 'config',
	});
	add({
		id: 'active-python',
		label: 'Active VS Code: Python interpreter',
		path: params.activePythonInterpreterPath ?? '',
		source: 'pythonExtension',
	});
	for (const path of params.pathCandidates ?? ['python3', 'python']) {
		add({
			id: `path-${path}`,
			label: `${path} from PATH`,
			path,
			source: 'path',
		});
	}
	return candidates;
};

export const selectedCandidate = (state: WizardState): SetupWizardInterpreterCandidate | undefined =>
	state.candidates.find((candidate) => candidate.id === state.selectedCandidateId);

export const visibleEnvironments = (state: WizardState): QiimeEnvironmentOption[] =>
	state.environments.filter((environment) => environment.platform === state.platform.id);

export const selectedEnvironment = (state: WizardState): QiimeEnvironmentOption | undefined =>
	visibleEnvironments(state).find(
		(environment) => environment.version === state.version && environment.distribution === state.distribution && environment.url === state.environmentUrl
	);

export const isSafeEnvironmentName = (value: string): boolean => /^[A-Za-z0-9._:-]+$/.test(String(value || ''));

export const isAllowedQiimeEnvironmentUrl = (value: string): boolean => {
	try {
		const url = new URL(String(value || ''));
		if (url.protocol !== 'https:' || !/\.ya?ml$/.test(url.pathname)) {
			return false;
		}
		if (url.hostname === 'packages.qiime2.org') {
			return url.pathname.startsWith('/qiime2/');
		}
		return url.hostname === 'raw.githubusercontent.com' && url.pathname.startsWith('/qiime2/distributions/refs/heads/dev/');
	} catch {
		return false;
	}
};

export const shellQuote = (value: string): string => `'${value.replace(/'/g, `'\''`)}'`;

export const environmentName = (state: WizardState): string => selectedEnvironment(state)?.environmentName || '';

export const environmentUrl = (state: WizardState): string => selectedEnvironment(state)?.url || '';

export const selectedInterpreterPath = (state: WizardState): string => state.interpreterPath || selectedCandidate(state)?.path || '';

export const inferredInterpreterPath = (state: WizardState): string => {
	if (state.route === 'existing') {
		return selectedInterpreterPath(state);
	}
	return state.interpreterPath || selectedCandidate(state)?.path || (state.manager === 'conda' && environmentName(state) ? '/opt/miniconda3/envs/' + environmentName(state) + '/bin/python' : 'python');
};

export const targetKey = (state: WizardState): string => {
	if (state.route === 'existing') {
		return 'existing:' + selectedInterpreterPath(state);
	}
	if (state.route === 'new') {
		return ['new', state.manager || '', state.version || '', state.distribution || '', environmentName(state), environmentUrl(state)].join(':');
	}
	return `${state.route}:`;
};

export const resetValidation = (state: WizardState): void => {
	state.qiimeStatus = 'unknown';
	state.q2lspStatus = 'unknown';
	state.q2lspVersion = '';
	state.savedInterpreterPath = false;
	state.validatedInterpreterPath = '';
	state.validatedTargetKey = '';
};

export const saveEnabled = (state: SetupWizardSaveState): boolean => {
	const normalize = (value: unknown): string => typeof value === 'string' ? value.trim() : '';
	const hasWizardCollections = Array.isArray((state as Partial<WizardState>).candidates)
		&& Array.isArray((state as Partial<WizardState>).environments);
	const path = normalize(state.interpreterPath) || (hasWizardCollections ? selectedInterpreterPath(state as WizardState) : '');
	if (!path || state.qiimeStatus !== 'ready' || state.q2lspStatus !== 'ready') {
		return false;
	}
	const currentTargetKey = normalize(state.targetKey)
		|| (hasWizardCollections ? targetKey(state as WizardState) : buildWizardTargetKey(state));
	return normalize(state.validatedInterpreterPath) === path
		&& normalize(state.validatedTargetKey) === currentTargetKey;
};

export const qiimeCommand = (state: WizardState): string => {
	if (state.metadataStatus !== 'ready' || !environmentUrl(state)) {
		return '';
	}
	if (state.manager === 'manual') {
		return 'Open QIIME 2 Quickstart, then return to validate your selected interpreter.';
	}
	if (!isAllowedQiimeEnvironmentUrl(environmentUrl(state)) || !isSafeEnvironmentName(environmentName(state))) {
		return '';
	}
	if (state.manager === 'pixi') {
		return 'pixi init && pixi import --format conda-env ' + shellQuote(environmentUrl(state)) + ' -e ' + shellQuote(environmentName(state)) + ' && pixi install';
	}
	const subdirPrefix = state.platform.condaSubdir ? 'CONDA_SUBDIR=' + shellQuote(state.platform.condaSubdir) + ' ' : '';
	return subdirPrefix + 'conda env create --name ' + shellQuote(environmentName(state)) + ' --file ' + shellQuote(environmentUrl(state));
};

export const q2lspInstallCommand = (state: WizardState): string => {
	if (state.route === 'existing') {
		return selectedInterpreterPath(state) ? shellQuote(selectedInterpreterPath(state)) + ' -m pip install -U q2lsp' : '';
	}
	if (state.manager === 'pixi') {
		return 'pixi run python -m pip install -U q2lsp';
	}
	if (state.manager === 'conda' && environmentName(state) && isSafeEnvironmentName(environmentName(state))) {
		return 'conda run -n ' + shellQuote(environmentName(state)) + ' python -m pip install -U q2lsp';
	}
	return shellQuote(inferredInterpreterPath(state)) + ' -m pip install -U q2lsp';
};

export const statusForStep = (route: SetupWizardRoute, index: number, state: WizardState): WizardStepStatus => {
	if (route === 'existing') {
		if (index === 0) {
			return state.interpreterPath || selectedCandidate(state) ? 'passed' : 'current';
		}
		if (index === 1) {
			return state.qiimeStatus === 'ready' ? 'passed' : state.qiimeStatus === 'missing' ? 'failed' : 'current';
		}
		if (index === 2) {
			return state.q2lspStatus === 'ready' ? 'passed' : state.q2lspStatus === 'missing' ? 'failed' : 'current';
		}
		if (index === 3) {
			return state.savedInterpreterPath ? 'passed' : 'current';
		}
		return state.savedInterpreterPath ? 'passed' : 'not started';
	}
	if (index === 0) {
		return state.manager ? 'passed' : 'current';
	}
	if (index === 1) {
		return state.manager === 'manual' || state.managerStatus === 'ready' ? 'passed' : state.managerStatus === 'missing' ? 'failed' : 'current';
	}
	if (index === 2) {
		return selectedEnvironment(state) ? 'passed' : 'current';
	}
	if (index === 3) {
		return state.submittedTarget ? 'passed' : 'current';
	}
	if (index === 4) {
		return state.qiimeStatus === 'ready' ? 'passed' : state.qiimeStatus === 'missing' ? 'failed' : 'current';
	}
	if (index === 5) {
		return state.q2lspStatus === 'ready' ? 'passed' : state.q2lspStatus === 'missing' ? 'failed' : 'current';
	}
	if (index === 6) {
		return state.savedInterpreterPath ? 'passed' : 'current';
	}
	return state.savedInterpreterPath ? 'passed' : 'not started';
};

export const switchManager = (state: WizardState, nextManager: string): void => {
	if (state.manager !== nextManager) {
		state.manager = nextManager;
		state.managerStatus = state.managerStatuses[nextManager] || 'unknown';
		state.submittedTarget = undefined;
		resetValidation(state);
	}
};

export const selectCandidate = (state: WizardState, candidateId: string): void => {
	state.selectedCandidateId = candidateId;
	state.interpreterPath = selectedCandidate(state)?.path || '';
	resetValidation(state);
};

const serializeFunction = (name: string, fn: { toString(): string }): string => {
	const source = fn.toString()
		.replace(/\(0, exports\.([A-Za-z0-9_]+)\)\(/g, '$1(')
		.replace(/exports\.([A-Za-z0-9_]+)/g, '$1');
	return `const ${name} = ${source};`;
};

export const serializeWebviewScriptFunctions = (): string => [
	serializeFunction('selectedCandidate', selectedCandidate),
	serializeFunction('visibleEnvironments', visibleEnvironments),
	serializeFunction('selectedEnvironment', selectedEnvironment),
	serializeFunction('isSafeEnvironmentName', isSafeEnvironmentName),
	serializeFunction('isAllowedQiimeEnvironmentUrl', isAllowedQiimeEnvironmentUrl),
	serializeFunction('shellQuote', shellQuote),
	serializeFunction('environmentName', environmentName),
	serializeFunction('environmentUrl', environmentUrl),
	serializeFunction('selectedInterpreterPath', selectedInterpreterPath),
	serializeFunction('inferredInterpreterPath', inferredInterpreterPath),
	serializeFunction('targetKey', targetKey),
	serializeFunction('resetValidation', resetValidation),
	serializeFunction('saveEnabled', saveEnabled),
	serializeFunction('qiimeCommand', qiimeCommand),
	serializeFunction('q2lspInstallCommand', q2lspInstallCommand),
	serializeFunction('statusForStep', statusForStep),
	serializeFunction('switchManager', switchManager),
	serializeFunction('selectCandidate', selectCandidate),
].join('\n');

export const buildSetupWizardHtml = (options: SetupWizardOptions): string => {
	const platform = options.platform ?? resolveQiimePlatform(process.platform, process.arch);
	const environments = (options.environments ?? []).filter((environment) => environment.platform === platform.id);
	const metadataStatus = options.metadataStatus ?? (environments.length > 0 ? 'ready' : 'loading');
	const interpreterCandidates = options.interpreterCandidates ?? buildSetupWizardInterpreterCandidates({
		configuredInterpreterPath: options.interpreterPath,
		activePythonInterpreterPath: options.activePythonInterpreterPath,
	});
	const initialVersion = resolveInitialQiimeVersion(environments);
	const initialDistributions = uniqueQiimeDistributions(environments.filter(
		(environment) => environment.version === initialVersion
	));
	const initialEnvironmentOptions = environments
		.filter((environment) => environment.version === initialVersion)
		.filter((environment) => environment.distribution === (initialDistributions[0] ?? ''))
		.sort((left, right) => left.fileName.localeCompare(right.fileName));
	const bootstrapState = serializeWebviewScriptState({
		interpreterPath: options.interpreterPath ?? interpreterCandidates[0]?.path ?? '',
		interpreterCandidates,
		managers: SETUP_WIZARD_MANAGERS,
		platform,
		environments,
		metadataStatus,
		initialVersion,
		initialDistribution: initialDistributions[0] ?? '',
		initialEnvironmentUrl: initialEnvironmentOptions[0]?.url ?? '',
	});

	const serializedFunctions = serializeWebviewScriptFunctions();

	return `<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${options.nonce}';">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>q2lsp Setup Wizard</title>
	<style>
		:root { color-scheme: dark; }
		body { color: var(--vscode-foreground); background: var(--vscode-editor-background); font-family: var(--vscode-font-family); font-size: var(--vscode-font-size); margin: 0; }
		button, select { font: inherit; }
		button:focus-visible, select:focus-visible, .card:focus-visible { outline: 2px solid var(--vscode-focusBorder); outline-offset: 2px; }
		.shell { box-sizing: border-box; display: grid; gap: 18px; max-width: 1120px; padding: 22px 24px; }
		h1 { font-size: 20px; margin: 0; }
		h2 { font-size: 18px; margin: 0; }
		h3 { font-size: 15px; margin: 0; }
		.main-grid { display: grid; gap: 16px; }
		@media (min-width: 900px) { .main-grid.has-route { grid-template-columns: 280px minmax(0, 1fr); } }
		.card, .panel { background: var(--vscode-sideBar-background); border: 1px solid var(--vscode-widget-border); color: var(--vscode-foreground); padding: 12px; transition: border-color 120ms ease, background 120ms ease; }
		.card:hover, button.action:hover:not(:disabled) { border-color: var(--vscode-focusBorder); }
		.route-grid, .option-grid, .candidate-list, .field-grid, .content-stack { display: grid; gap: 10px; }
		@media (min-width: 760px) { .route-grid, .field-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
		.route-card, .option-card { cursor: pointer; text-align: left; }
		.is-selected { border-color: var(--vscode-focusBorder); box-shadow: inset 3px 0 0 var(--vscode-focusBorder); }
		.checklist { display: grid; gap: 8px; margin: 0; padding: 0; }
		.checklist li { align-items: start; display: grid; gap: 8px; grid-template-columns: auto 1fr; list-style: none; }
		.badge { border: 1px solid currentColor; border-radius: 999px; color: var(--vscode-descriptionForeground); font-size: 11px; padding: 1px 7px; }
		.badge.current { color: var(--vscode-focusBorder); } .badge.passed { color: var(--vscode-testing-iconPassed); } .badge.failed { color: var(--vscode-testing-iconFailed); }
		.meta, .muted, .candidate-path { color: var(--vscode-descriptionForeground); }
		.candidate-status { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
		.status-ready { color: var(--vscode-testing-iconPassed); } .status-missing, .error { color: var(--vscode-testing-iconFailed); }
		[role="alert"] { border-color: var(--vscode-testing-iconFailed); }
		.command-box { background: var(--vscode-textCodeBlock-background); border: 1px solid var(--vscode-widget-border); display: grid; gap: 8px; padding: 10px; }
		code { color: var(--vscode-textPreformat-foreground); font-family: var(--vscode-editor-font-family); white-space: pre-wrap; word-break: break-word; }
		.actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
		.action { background: var(--vscode-button-secondaryBackground); border: 1px solid var(--vscode-button-border, transparent); color: var(--vscode-button-secondaryForeground); cursor: pointer; padding: 6px 11px; }
		.action.primary { background: var(--vscode-button-background); color: var(--vscode-button-foreground); font-weight: 600; }
		.action:disabled { cursor: not-allowed; opacity: 0.5; }
		label { display: grid; gap: 5px; font-weight: 600; } select { background: var(--vscode-dropdown-background); border: 1px solid var(--vscode-dropdown-border); color: var(--vscode-dropdown-foreground); padding: 6px 8px; }
		.screen[hidden], .route-panel[hidden], .metadata-error[hidden], .submitted-target[hidden], .manager-missing[hidden] { display: none; }
	</style>
</head>
<body>
	<div class="shell">
		<header class="content-stack">
			<h1>q2lsp Setup Wizard</h1>
			<p class="muted">Connect an existing QIIME 2 environment or create a new one. Terminal commands never count as success; validate after commands finish.</p>
			<div id="globalStatus" role="status" aria-live="polite" class="panel"></div>
		</header>
		<main id="mainGrid" class="main-grid">
			<section class="screen content-stack" id="routeScreen">
				<h2>What do you want to do?</h2>
				<div class="route-grid">
					<button type="button" class="card route-card" data-route="existing">
						<h3>Use existing QIIME 2 environment</h3>
						<p class="muted">Pick and validate a Python interpreter that already has QIIME 2.</p>
					</button>
					<button type="button" class="card route-card" data-route="new">
						<h3>Create new QIIME 2 environment</h3>
						<p class="muted">Choose Conda, Pixi, or Manual and validate each result.</p>
					</button>
				</div>
			</section>

			<aside id="checklistPanel" class="panel route-panel" hidden>
				<h2 id="checklistTitle">Setup checklist</h2>
				<ol id="checklist" class="checklist" aria-label="Setup checklist"></ol>
			</aside>

			<section id="existingRoute" class="route-panel content-stack" hidden>
				<h2>Use existing QIIME 2 environment</h2>
				<div class="candidate-list" id="candidateList"></div>
				<div class="actions">
					<button type="button" class="action" data-command="browseInterpreter">Browse for another Python interpreter</button>
					<button type="button" class="action" data-command="validateEnvironment">Validate QIIME 2</button>
					<button type="button" class="action" data-command="validateQ2lsp">Validate q2lsp</button>
					<button type="button" class="action primary" id="saveExistingInterpreterPath" data-command="saveInterpreterPath" disabled>Save interpreter path</button>
				</div>
				<div class="panel" id="existingRecovery" role="alert" hidden>
					<p>QIIME 2 Missing. Choose another interpreter, create a new QIIME 2 environment, or show log.</p>
					<div class="actions"><button type="button" class="action" data-route="new">Create new QIIME 2 environment</button><button type="button" class="action" data-command="showLog">Show log</button></div>
				</div>
			</section>

			<section id="newRoute" class="route-panel content-stack" hidden>
				<h2>Create new QIIME 2 environment</h2>
				<div class="option-grid" id="managerCards"></div>
				<div class="panel manager-missing" id="managerMissing" role="alert">
					<p><strong>Conda was not found.</strong></p>
					<p>Install Miniconda, then check again.</p>
					<div class="actions"><button type="button" class="action primary" data-command="installManager">Install Miniconda in Terminal</button><button type="button" class="action" data-command="checkManager">I installed it — check again</button></div>
				</div>
				<div class="metadata-error panel" id="metadataError" role="alert" hidden>
					<p><strong>Could not load QIIME 2 environment metadata.</strong></p>
					<p>The Setup Wizard needs the official QIIME 2 environment list before it can create a command.</p>
					<div class="actions"><button type="button" class="action" data-command="retryQiimeMetadata">Retry</button><button type="button" class="action" data-command="openQiimeQuickstart">Open QIIME 2 Quickstart</button></div>
				</div>
				<div class="field-grid" id="targetSelectors" data-metadata-required>
					<label>Version<select id="versionSelect"></select></label>
					<label>Distribution<select id="distributionSelect"></select></label>
				</div>
				<details>
					<summary>Advanced details</summary>
					<label>Environment file URL<select id="environmentUrlSelect" disabled></select></label>
				</details>
				<div class="command-box" id="qiimeCommandBox"><code id="qiimeCommand">Loading QIIME 2 environment metadata...</code></div>
				<div id="submittedTarget" class="panel submitted-target" hidden>
					<p><strong>Command sent to Terminal for:</strong></p>
					<p id="submittedTargetSummary"></p>
					<div class="actions"><button type="button" class="action primary" data-command="validateEnvironment">Validate QIIME 2</button><button type="button" class="action" id="changeTargetAction">Change target</button></div>
				</div>
				<div class="actions">
					<button type="button" class="action" data-command="checkManager">Check installation</button>
					<button type="button" class="action primary" id="createEnvironmentAction" data-command="createQiimeEnvironment">Create environment in Terminal</button>
				</div>
			</section>

			<section id="q2lspPanel" class="route-panel content-stack" hidden>
				<h2>Install or validate q2lsp</h2>
				<div class="command-box"><code id="q2lspCommand"></code></div>
				<p id="q2lspVersionInfo" class="muted">Server package: <span id="q2lspVersionValue">not validated</span></p>
				<div class="actions"><button type="button" class="action primary" data-command="installQ2lsp">Install q2lsp in Terminal</button><button type="button" class="action" data-command="validateQ2lsp">Validate q2lsp</button><button type="button" class="action" id="saveInterpreterPathAction" data-command="saveInterpreterPath" disabled>Save interpreter path</button></div>
			</section>
		</main>
	</div>
	<script nonce="${options.nonce}">
		const vscode = acquireVsCodeApi();
		const bootstrap = ${bootstrapState};
		const state = {
			route: 'start',
			manager: 'conda',
			managerStatus: 'unknown',
			managerStatuses: {},
			qiimeStatus: 'unknown',
			q2lspStatus: 'unknown',
			q2lspVersion: '',
			pendingCommand: '',
			statusMessage: '',
			selectedCandidateId: bootstrap.interpreterCandidates[0]?.id || '',
			interpreterPath: bootstrap.interpreterPath,
			candidates: bootstrap.interpreterCandidates,
			environments: bootstrap.environments,
			metadataStatus: bootstrap.metadataStatus,
			version: bootstrap.initialVersion,
			distribution: bootstrap.initialDistribution,
			environmentUrl: bootstrap.initialEnvironmentUrl,
			platform: bootstrap.platform,
			submittedTarget: undefined,
			savedInterpreterPath: false,
		};
		const existingSteps = ${JSON.stringify(SETUP_WIZARD_EXISTING_ROUTE_STEPS)};
		const newSteps = ${JSON.stringify(SETUP_WIZARD_NEW_ROUTE_STEPS)};
		const uniqueValues = (values) => Array.from(new Set(values)).sort((left, right) => right.localeCompare(left, undefined, { numeric: true }));
		const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
		${serializedFunctions}
		const updateSelectors = () => {
			const environmentsForPlatform = visibleEnvironments(state);
			const versions = uniqueValues(environmentsForPlatform.map((environment) => environment.version));
			if (!versions.includes(state.version)) state.version = versions[0] || '';
			document.getElementById('versionSelect').innerHTML = versions.map((version) => '<option value="' + escapeHtml(version) + '">' + escapeHtml(version) + '</option>').join('');
			document.getElementById('versionSelect').value = state.version;
			const distributions = Array.from(new Set(environmentsForPlatform.filter((environment) => environment.version === state.version).map((environment) => environment.distribution))).sort();
			if (!distributions.includes(state.distribution)) state.distribution = distributions[0] || '';
			document.getElementById('distributionSelect').innerHTML = distributions.map((distribution) => '<option value="' + escapeHtml(distribution) + '">' + escapeHtml(distribution) + '</option>').join('');
			document.getElementById('distributionSelect').value = state.distribution;
			const envs = environmentsForPlatform.filter((environment) => environment.version === state.version && environment.distribution === state.distribution).sort((left, right) => left.fileName.localeCompare(right.fileName));
			if (!envs.some((environment) => environment.url === state.environmentUrl)) state.environmentUrl = envs[0]?.url || '';
			document.getElementById('environmentUrlSelect').innerHTML = envs.map((environment) => '<option value="' + escapeHtml(environment.url) + '">' + escapeHtml(environment.url) + '</option>').join('');
			document.getElementById('environmentUrlSelect').value = state.environmentUrl;
		};
		const renderChecklist = () => {
			const steps = state.route === 'existing' ? existingSteps : newSteps;
			document.getElementById('checklist').innerHTML = steps.map((step, index) => {
				const status = statusForStep(state.route, index, state);
				return '<li><span class="badge ' + escapeHtml(status) + '">' + escapeHtml(status) + '</span><span>' + escapeHtml(step.label) + '</span></li>';
			}).join('');
		};
		const renderCandidates = () => {
			document.getElementById('candidateList').innerHTML = state.candidates.map((candidate) => '<button type="button" class="card candidate-card ' + (candidate.id === state.selectedCandidateId ? 'is-selected' : '') + '" data-candidate-id="' + escapeHtml(candidate.id) + '"><strong>' + escapeHtml(candidate.label) + '</strong><span class="candidate-path">' + escapeHtml(candidate.path) + '</span><span class="candidate-status"><span>QIIME 2: <span class="status-' + escapeHtml(candidate.qiimeStatus || 'missing') + '">' + (candidate.qiimeStatus === 'ready' ? 'Ready' : candidate.available === false ? 'Unavailable' : 'Missing') + '</span></span><span>q2lsp: <span class="status-' + escapeHtml(candidate.q2lspStatus || 'missing') + '">' + (candidate.q2lspStatus === 'ready' ? 'Ready' : 'Missing') + '</span></span></span></button>').join('');
			for (const card of document.querySelectorAll('[data-candidate-id]')) card.addEventListener('click', () => { selectCandidate(state, card.dataset.candidateId); render(); });
		};
		const renderManagers = () => {
			document.getElementById('managerCards').innerHTML = bootstrap.managers.map((manager) => '<button type="button" class="card option-card ' + (manager.id === state.manager ? 'is-selected' : '') + '" data-manager="' + escapeHtml(manager.id) + '"><strong>' + escapeHtml(manager.label) + '</strong><span class="muted">' + escapeHtml(manager.description) + '</span></button>').join('');
			for (const card of document.querySelectorAll('[data-manager]')) card.addEventListener('click', () => { switchManager(state, card.dataset.manager); render(); });
		};
		const render = () => {
			updateSelectors();
			document.getElementById('mainGrid').classList.toggle('has-route', state.route !== 'start');
			document.getElementById('routeScreen').hidden = state.route !== 'start';
			document.getElementById('checklistPanel').hidden = state.route === 'start';
			document.getElementById('existingRoute').hidden = state.route !== 'existing';
			document.getElementById('newRoute').hidden = state.route !== 'new';
			document.getElementById('q2lspPanel').hidden = state.route === 'start';
			document.getElementById('globalStatus').textContent = state.pendingCommand ? 'Running ' + state.pendingCommand + '...' : state.statusMessage;
			const qiimeCommandText = qiimeCommand(state);
			document.getElementById('metadataError').hidden = state.metadataStatus !== 'missing';
			document.getElementById('targetSelectors').hidden = state.metadataStatus !== 'ready' || !!state.submittedTarget;
			document.getElementById('createEnvironmentAction').disabled = state.metadataStatus !== 'ready' || !qiimeCommandText || !!state.submittedTarget || (state.manager !== 'manual' && state.managerStatus !== 'ready');
			document.getElementById('managerMissing').hidden = state.manager === 'manual' || state.managerStatus !== 'missing';
			document.getElementById('existingRecovery').hidden = state.qiimeStatus !== 'missing';
			document.getElementById('saveExistingInterpreterPath').disabled = !saveEnabled(state);
			document.getElementById('saveInterpreterPathAction').disabled = !saveEnabled(state);
			document.getElementById('qiimeCommandBox').hidden = !qiimeCommandText;
			document.getElementById('qiimeCommand').textContent = qiimeCommandText || 'Load QIIME 2 environment metadata before creating a command.';
			document.getElementById('q2lspCommand').textContent = q2lspInstallCommand(state);
			document.getElementById('q2lspVersionValue').textContent = state.q2lspVersion || 'not validated';
			document.getElementById('submittedTarget').hidden = !state.submittedTarget;
			document.getElementById('submittedTargetSummary').textContent = state.submittedTarget ? 'QIIME 2 ' + state.submittedTarget.version + ' ' + state.submittedTarget.distribution + ' — Environment: ' + state.submittedTarget.environmentName : '';
			renderChecklist(); renderCandidates(); renderManagers();
			for (const button of document.querySelectorAll('[data-command]')) button.disabled = !!state.pendingCommand && button.dataset.command === state.pendingCommand;
		};
		document.getElementById('versionSelect').addEventListener('change', (event) => { state.version = event.target.value; state.environmentUrl = ''; state.submittedTarget = undefined; resetValidation(state); render(); });
		document.getElementById('distributionSelect').addEventListener('change', (event) => { state.distribution = event.target.value; state.environmentUrl = ''; state.submittedTarget = undefined; resetValidation(state); render(); });
		document.getElementById('environmentUrlSelect').addEventListener('change', (event) => { state.environmentUrl = event.target.value; state.submittedTarget = undefined; resetValidation(state); render(); });
		document.getElementById('changeTargetAction').addEventListener('click', () => { state.submittedTarget = undefined; resetValidation(state); render(); });
		for (const routeButton of document.querySelectorAll('[data-route]')) routeButton.addEventListener('click', () => { if (state.route !== routeButton.dataset.route) resetValidation(state); state.route = routeButton.dataset.route; render(); });
		document.addEventListener('click', (event) => {
			const button = event.target.closest('[data-command]');
			if (!button) return;
			const command = button.dataset.command;
			state.pendingCommand = command;
			vscode.postMessage({ command, commandText: command === 'createQiimeEnvironment' ? qiimeCommand(state) : command === 'installQ2lsp' ? q2lspInstallCommand(state) : undefined, route: state.route, interpreterPath: inferredInterpreterPath(state), manager: state.manager, version: state.version, distribution: state.distribution, environmentName: environmentName(state), environmentUrl: environmentUrl(state), condaSubdir: state.platform.condaSubdir, qiimeStatus: state.qiimeStatus, q2lspStatus: state.q2lspStatus, validatedInterpreterPath: state.validatedInterpreterPath, validatedTargetKey: state.validatedTargetKey, targetKey: targetKey(state) });
			render();
		});
		window.addEventListener('message', (event) => {
			if (event.data?.type === 'qiimeManifest') { state.environments = event.data.environments; state.metadataStatus = event.data.environments.length > 0 ? 'ready' : 'missing'; state.environmentUrl = ''; state.pendingCommand = ''; resetValidation(state); render(); return; }
			if (event.data?.type !== 'wizardStatus') return;
			const patch = event.data.patch || {};
			if (Array.isArray(patch.candidates)) {
				const mergedCandidates = new Map(state.candidates.map((candidate) => [candidate.id, candidate]));
				for (const candidate of patch.candidates) mergedCandidates.set(candidate.id, { ...(mergedCandidates.get(candidate.id) || {}), ...candidate });
				patch.candidates = Array.from(mergedCandidates.values());
			}
			if (patch.checkedManager) {
				state.managerStatuses[patch.checkedManager] = patch.managerStatus;
				if (patch.checkedManager !== state.manager) delete patch.managerStatus;
				delete patch.checkedManager;
			}
			Object.assign(state, patch); state.pendingCommand = ''; render();
		});
		render();
	</script>
</body>
</html>`;
};

const serializeWebviewScriptState = (state: unknown): string => JSON.stringify(state)
	.replace(/</g, '\\u003c')
	.replace(/>/g, '\\u003e')
	.replace(/&/g, '\\u0026')
	.replace(/\u2028/g, '\\u2028')
	.replace(/\u2029/g, '\\u2029');

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
