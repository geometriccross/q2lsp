import * as assert from 'assert';
import type * as vscode from 'vscode';
import {
	SETUP_WIZARD_EXISTING_ROUTE_STEPS,
	SETUP_WIZARD_MANAGERS,
	SETUP_WIZARD_NEW_ROUTE_STEPS,
	buildFallbackQiimeEnvironments,
	buildQiimeEnvironmentsFromTree,
	buildManagerInstallCommand,
	buildQ2lspInstallCommand,
	buildSetupWizardHtml,
	buildSetupWizardInterpreterCandidates,
	buildSyntheticQiimeEnvironment,
	buildWizardTargetKey,
	mergeQiimeEnvironments,
	parseQiimeEnvironmentPath,
	resolveQiimePlatform,
	WizardState,
	QiimeEnvironmentOption,
	resetValidation,
	saveEnabled,
	qiimeCommand,
	statusForStep,
	switchManager,
	selectCandidate,
	targetKey,
	serializeWebviewScriptFunctions,
	selectedInterpreterPath,
	q2lspInstallCommand,
	handleSetupWizardMessage,
	type WizardExecutors,
} from '../setupWizard/index';

suite('q2lsp setup wizard tests', () => {
	const makeState = (overrides: Partial<WizardState> = {}): WizardState => ({
		route: 'start',
		manager: 'conda',
		managerStatus: 'unknown',
		managerStatuses: {},
		qiimeStatus: 'unknown',
		q2lspStatus: 'unknown',
		q2lspVersion: '',
		pendingCommand: '',
		statusMessage: '',
		selectedCandidateId: '',
		interpreterPath: '',
		candidates: [],
		environments: [],
		metadataStatus: 'loading',
		version: '',
		distribution: '',
		environmentUrl: '',
		platform: { id: 'linux-64', label: 'Linux x64' },
		submittedTarget: undefined,
		savedInterpreterPath: false,
		validatedInterpreterPath: '',
		validatedTargetKey: '',
		...overrides,
	});

	const makeEnvironment = (overrides: Partial<QiimeEnvironmentOption> = {}): QiimeEnvironmentOption => ({
		version: '2026.4',
		distribution: 'tiny',
		platform: 'linux-64',
		fileName: 'qiime2-tiny-2026.4-linux-64-conda.yml',
		url: 'https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-linux-64-conda.yml',
		environmentName: 'qiime2-tiny-2026.4',
		...overrides,
	});

	// Captures every message the host posts back to the webview.
	const makeCapturingWebview = (): { webview: vscode.Webview; posted: Array<Record<string, unknown>> } => {
		const posted: Array<Record<string, unknown>> = [];
		const webview = {
			postMessage: async (message: unknown): Promise<boolean> => {
				posted.push(message as Record<string, unknown>);
				return true;
			},
		} as unknown as vscode.Webview;
		return { webview, posted };
	};

	// Finds the last wizardStatus patch carrying a given field value.
	const findPatch = (posted: Array<Record<string, unknown>>, field: string, value: unknown): Record<string, unknown> | undefined => {
		const patches = posted
			.filter((message) => message.type === 'wizardStatus')
			.map((message) => message.patch as Record<string, unknown> | undefined);
		for (let index = patches.length - 1; index >= 0; index -= 1) {
			const patch = patches[index];
			if (patch && patch[field] === value) {
				return patch;
			}
		}
		return undefined;
	};

	test('existing route validation success stamps validated target identity (tracer bullet)', async () => {
		const { webview, posted } = makeCapturingWebview();
		const executors: WizardExecutors = {
			runPythonValidation: async () => ({ ok: true }),
			validateInterpreter: async () => ({ ok: true }),
			resolveEnvironmentInterpreter: async () => ({ ok: false, message: 'no conda environment in existing route test' }),
		};

		await handleSetupWizardMessage({
			message: { command: 'validateEnvironment', route: 'existing', interpreterPath: '/env-a/bin/python' },
			webview,
			executors,
		});

		const patch = findPatch(posted, 'qiimeStatus', 'ready');
		assert.ok(patch, 'expected a ready status patch after QIIME 2 validation passes');
		assert.strictEqual(patch!.validatedInterpreterPath, '/env-a/bin/python');
		assert.strictEqual(patch!.validatedTargetKey, 'existing:/env-a/bin/python');
	});

	test('new route conda resolution stamps validated target bound to manager and target identity', async () => {
		const { webview, posted } = makeCapturingWebview();
		const message = {
			command: 'validateEnvironment',
			route: 'new',
			manager: 'conda',
			version: '2026.4',
			distribution: 'tiny',
			environmentName: 'qiime2-tiny-2026.4',
			environmentUrl: 'https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-linux-64-conda.yml',
		};
		const executors: WizardExecutors = {
			runPythonValidation: async () => ({ ok: true }),
			validateInterpreter: async () => ({ ok: true }),
			resolveEnvironmentInterpreter: async () => ({ ok: true, interpreterPath: '/conda-env/bin/python' }),
		};

		await handleSetupWizardMessage({ message, webview, executors });

		const patch = findPatch(posted, 'qiimeStatus', 'ready');
		assert.ok(patch, 'expected a ready status patch after QIIME 2 validation passes');
		assert.strictEqual(patch!.validatedInterpreterPath, '/conda-env/bin/python');
		assert.strictEqual(
			patch!.validatedTargetKey,
			buildWizardTargetKey({ ...message, interpreterPath: '/conda-env/bin/python' })
		);
	});

	test('existing route never resolves a conda environment even when manager and environment name linger', async () => {
		const { webview, posted } = makeCapturingWebview();
		// Stale new-route fields remain in the message, but the user is on the
		// existing route with an explicit interpreter selected.
		const condaCalled: string[] = [];
		const executors: WizardExecutors = {
			runPythonValidation: async () => ({ ok: true }),
			validateInterpreter: async () => ({ ok: true }),
			resolveEnvironmentInterpreter: async (manager, environmentName) => {
				condaCalled.push(`${manager}:${environmentName ?? ''}`);
				return { ok: true, interpreterPath: '/conda-env/bin/python' };
			},
		};

		await handleSetupWizardMessage({
			message: {
				command: 'validateEnvironment',
				route: 'existing',
				interpreterPath: '/explicit/bin/python',
				manager: 'conda',
				environmentName: 'qiime2-tiny-2026.4',
			},
			webview,
			executors,
		});

		assert.deepStrictEqual(condaCalled, [], 'existing route must not resolve a conda environment');
		const patch = findPatch(posted, 'qiimeStatus', 'ready');
		assert.ok(patch, 'expected validation to pass for the explicit interpreter');
		assert.strictEqual(patch!.validatedInterpreterPath, '/explicit/bin/python');
	});

	test('q2lsp validation does not mark QIIME 2 as ready', async () => {
		const { webview, posted } = makeCapturingWebview();
		const executors: WizardExecutors = {
			runPythonValidation: async () => ({ ok: true }),
			validateInterpreter: async () => ({ ok: true }),
			resolveEnvironmentInterpreter: async () => ({ ok: false, message: 'no conda environment' }),
		};

		await handleSetupWizardMessage({
			message: { command: 'validateQ2lsp', route: 'existing', interpreterPath: '/env/bin/python' },
			webview,
			executors,
		});

		const q2lspPatch = posted
			.filter((message) => message.type === 'wizardStatus')
			.map((message) => message.patch as Record<string, unknown>)
			.find((patch) => patch.q2lspStatus === 'ready');
		assert.ok(q2lspPatch, 'expected q2lsp validation to pass');
		assert.notStrictEqual(q2lspPatch!.qiimeStatus, 'ready', 'q2lsp validation must not mark QIIME 2 as ready');
	});

	test('save is reachable after both validations pass for the existing route', async () => {
		const { webview, posted } = makeCapturingWebview();
		const executors: WizardExecutors = {
			runPythonValidation: async () => ({ ok: true }),
			validateInterpreter: async () => ({ ok: true }),
			resolveEnvironmentInterpreter: async () => ({ ok: false, message: 'no conda environment' }),
		};
		const message = { command: '', route: 'existing', interpreterPath: '/env/bin/python' } as const;

		await handleSetupWizardMessage({ message: { ...message, command: 'validateEnvironment' }, webview, executors });
		await handleSetupWizardMessage({ message: { ...message, command: 'validateQ2lsp' }, webview, executors });

		// Reconstruct the webview state by applying every status patch in order.
		const patched = makeState({ route: 'existing', interpreterPath: '/env/bin/python' });
		for (const postedMessage of posted) {
			if (postedMessage.type === 'wizardStatus') {
				Object.assign(patched, postedMessage.patch);
			}
		}

		assert.strictEqual(patched.qiimeStatus, 'ready');
		assert.strictEqual(patched.q2lspStatus, 'ready');
		assert.strictEqual(saveEnabled(patched), true);
	});

	test('existing validation is bound to the selected interpreter identity', () => {
		assert.strictEqual(buildWizardTargetKey({ route: 'existing', interpreterPath: '/env-a/bin/python' }), 'existing:/env-a/bin/python');
		const base = makeState({
			route: 'existing',
			interpreterPath: '/env-a/bin/python',
			qiimeStatus: 'ready',
			q2lspStatus: 'ready',
			validatedInterpreterPath: '/env-a/bin/python',
			validatedTargetKey: 'existing:/env-a/bin/python',
		});
		assert.strictEqual(saveEnabled(base), true);
		assert.strictEqual(saveEnabled({ ...base, interpreterPath: '/env-b/bin/python' }), false);
	});

	test('new environment validation is bound to route manager and target identity', () => {
		const env = makeEnvironment({
			url: 'https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-linux-conda.yml',
			environmentName: 'qiime2-tiny-2026.4',
		});
		const targetA = {
			route: 'new' as const,
			manager: 'conda',
			version: '2026.4',
			distribution: 'tiny',
			environmentName: 'qiime2-tiny-2026.4',
			environmentUrl: 'https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-linux-conda.yml',
		};
		const stateForKey = makeState({
			...targetA,
			environments: [env],
			version: '2026.4',
			distribution: 'tiny',
			environmentUrl: 'https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-linux-conda.yml',
			interpreterPath: '/env-a/bin/python',
		});
		const targetKeyA = targetKey(stateForKey);

		const base = makeState({
			...targetA,
			environments: [env],
			version: '2026.4',
			distribution: 'tiny',
			environmentUrl: 'https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-linux-conda.yml',
			interpreterPath: '/env-a/bin/python',
			qiimeStatus: 'ready',
			q2lspStatus: 'ready',
			validatedInterpreterPath: '/env-a/bin/python',
			validatedTargetKey: targetKeyA,
		});
		assert.strictEqual(saveEnabled(base), true);
		assert.strictEqual(saveEnabled({ ...base, distribution: 'amplicon' }), false);
		assert.strictEqual(saveEnabled({ ...base, route: 'existing' }), false);
	});

	test('statusForStep reflects existing route checklist state', () => {
		const base = makeState({ route: 'existing' });
		assert.strictEqual(statusForStep('existing', 0, base), 'current');
		assert.strictEqual(statusForStep('existing', 0, { ...base, interpreterPath: '/usr/bin/python' }), 'passed');
		assert.strictEqual(statusForStep('existing', 1, { ...base, qiimeStatus: 'ready' }), 'passed');
		assert.strictEqual(statusForStep('existing', 1, { ...base, qiimeStatus: 'missing' }), 'failed');
		assert.strictEqual(statusForStep('existing', 2, { ...base, q2lspStatus: 'ready' }), 'passed');
		assert.strictEqual(statusForStep('existing', 2, { ...base, q2lspStatus: 'missing' }), 'failed');
		assert.strictEqual(statusForStep('existing', 3, { ...base, savedInterpreterPath: true }), 'passed');
		assert.strictEqual(statusForStep('existing', 4, { ...base, savedInterpreterPath: true }), 'passed');
		assert.strictEqual(statusForStep('existing', 4, base), 'not started');
	});

	test('statusForStep reflects new route checklist state', () => {
		const base = makeState({ route: 'new', manager: 'conda' });
		assert.strictEqual(statusForStep('new', 0, base), 'passed');
		assert.strictEqual(statusForStep('new', 1, { ...base, managerStatus: 'ready' }), 'passed');
		assert.strictEqual(statusForStep('new', 1, { ...base, managerStatus: 'missing' }), 'failed');
		assert.strictEqual(statusForStep('new', 1, { ...base, manager: 'manual' }), 'passed');
		const withEnv = {
			...base,
			environments: [makeEnvironment()],
			metadataStatus: 'ready' as const,
			version: '2026.4',
			distribution: 'tiny',
			environmentUrl: 'https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-linux-64-conda.yml',
		};
		assert.strictEqual(statusForStep('new', 2, withEnv), 'passed');
		assert.strictEqual(statusForStep('new', 3, {
			...withEnv,
			submittedTarget: {
				version: '2026.4',
				distribution: 'tiny',
				environmentName: 'qiime2-tiny-2026.4',
				environmentUrl: 'https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-linux-64-conda.yml',
			},
		}), 'passed');
		assert.strictEqual(statusForStep('new', 4, { ...withEnv, qiimeStatus: 'ready' }), 'passed');
		assert.strictEqual(statusForStep('new', 4, { ...withEnv, qiimeStatus: 'missing' }), 'failed');
		assert.strictEqual(statusForStep('new', 5, { ...withEnv, q2lspStatus: 'ready' }), 'passed');
		assert.strictEqual(statusForStep('new', 6, { ...withEnv, savedInterpreterPath: true }), 'passed');
		assert.strictEqual(statusForStep('new', 7, { ...withEnv, savedInterpreterPath: true }), 'passed');
		assert.strictEqual(statusForStep('new', 7, withEnv), 'not started');
	});

	test('saveEnabled requires ready statuses and matching identity', () => {
		const base = makeState({
			route: 'existing',
			interpreterPath: '/env/bin/python',
			qiimeStatus: 'ready',
			q2lspStatus: 'ready',
			validatedInterpreterPath: '/env/bin/python',
			validatedTargetKey: 'existing:/env/bin/python',
		});
		assert.strictEqual(saveEnabled(base), true);
		assert.strictEqual(saveEnabled({ ...base, qiimeStatus: 'missing' }), false);
		assert.strictEqual(saveEnabled({ ...base, q2lspStatus: 'missing' }), false);
		assert.strictEqual(saveEnabled({ ...base, interpreterPath: '/other/bin/python' }), false);
		assert.strictEqual(saveEnabled({ ...base, validatedTargetKey: 'existing:/other/bin/python' }), false);
		assert.strictEqual(saveEnabled({ ...base, validatedInterpreterPath: '' }), false);
	});

	test('saveEnabled accepts server-side wizard message identity', () => {
		assert.strictEqual(saveEnabled({
			route: 'new',
			interpreterPath: '/env/bin/python',
			qiimeStatus: 'ready',
			q2lspStatus: 'ready',
			validatedInterpreterPath: '/env/bin/python',
			validatedTargetKey: 'new:conda:2026.4:tiny:qiime2-tiny-2026.4:https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-linux-64-conda.yml',
			targetKey: 'new:conda:2026.4:tiny:qiime2-tiny-2026.4:https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-linux-64-conda.yml',
		}), true);
	});

	test('resetValidation clears validation fields', () => {
		const state = makeState({
			qiimeStatus: 'ready',
			q2lspStatus: 'ready',
			q2lspVersion: '1.0.0',
			savedInterpreterPath: true,
			validatedInterpreterPath: '/env/bin/python',
			validatedTargetKey: 'existing:/env/bin/python',
		});
		resetValidation(state);
		assert.strictEqual(state.qiimeStatus, 'unknown');
		assert.strictEqual(state.q2lspStatus, 'unknown');
		assert.strictEqual(state.q2lspVersion, '');
		assert.strictEqual(state.savedInterpreterPath, false);
		assert.strictEqual(state.validatedInterpreterPath, '');
		assert.strictEqual(state.validatedTargetKey, '');
	});

	test('qiimeCommand returns empty when metadata is unavailable', () => {
		assert.strictEqual(qiimeCommand(makeState({ metadataStatus: 'loading' })), '');
		assert.strictEqual(qiimeCommand(makeState({ metadataStatus: 'missing' })), '');
	});

	test('qiimeCommand returns manual message for manual manager', () => {
		const state = makeState({
			route: 'new',
			manager: 'manual',
			metadataStatus: 'ready',
			environments: [makeEnvironment()],
			version: '2026.4',
			distribution: 'tiny',
			environmentUrl: 'https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-linux-64-conda.yml',
		});
		assert.strictEqual(qiimeCommand(state), 'Open QIIME 2 Quickstart, then return to validate your selected interpreter.');
	});

	test('qiimeCommand validates URL and environment name safety', () => {
		const safe = makeState({
			route: 'new',
			manager: 'conda',
			metadataStatus: 'ready',
			environments: [makeEnvironment()],
			version: '2026.4',
			distribution: 'tiny',
			environmentUrl: 'https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-linux-64-conda.yml',
		});
		assert.ok(qiimeCommand(safe).includes('conda env create'));
		const pixi = { ...safe, manager: 'pixi' };
		assert.strictEqual(
			qiimeCommand(pixi),
			"pixi init && pixi import --format conda-env 'https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-linux-64-conda.yml' -e 'qiime2-tiny-2026.4' && pixi install"
		);

		const unsafeUrl = { ...safe, environmentUrl: 'https://evil.com/env.yml' };
		assert.strictEqual(qiimeCommand(unsafeUrl), '');

		const unsafeName = makeState({
			route: 'new',
			manager: 'conda',
			metadataStatus: 'ready',
			environments: [makeEnvironment({ environmentName: 'evil; rm -rf /' })],
			version: '2026.4',
			distribution: 'tiny',
			environmentUrl: 'https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-linux-64-conda.yml',
		});
		assert.strictEqual(qiimeCommand(unsafeName), '');
	});

	test('qiimeCommand includes conda subdir when platform provides it', () => {
		const state = makeState({
			route: 'new',
			manager: 'conda',
			metadataStatus: 'ready',
			platform: { id: 'osx-64', label: 'macOS x64', condaSubdir: 'osx-64' },
			environments: [makeEnvironment({ platform: 'osx-64', fileName: 'qiime2-tiny-2026.4-osx-64-conda.yml', url: 'https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-osx-64-conda.yml' })],
			version: '2026.4',
			distribution: 'tiny',
			environmentUrl: 'https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-osx-64-conda.yml',
		});
		assert.ok(qiimeCommand(state).startsWith("CONDA_SUBDIR='osx-64' conda env create"));
	});

	test('switchManager updates state and resets validation when manager changes', () => {
		const state = makeState({ manager: 'conda', managerStatus: 'ready', managerStatuses: { conda: 'ready' }, qiimeStatus: 'ready', q2lspStatus: 'ready' });
		switchManager(state, 'pixi');
		assert.strictEqual(state.manager, 'pixi');
		assert.strictEqual(state.managerStatus, 'unknown');
		assert.strictEqual(state.submittedTarget, undefined);
		assert.strictEqual(state.qiimeStatus, 'unknown');
		assert.strictEqual(state.q2lspStatus, 'unknown');

		switchManager(state, 'pixi'); // no-op
		assert.strictEqual(state.manager, 'pixi');
	});

	test('selectCandidate updates interpreter path and resets validation', () => {
		const state = makeState({
			candidates: [
				{ id: 'c1', label: 'A', path: '/a/bin/python', source: 'config' },
				{ id: 'c2', label: 'B', path: '/b/bin/python', source: 'path' },
			],
			selectedCandidateId: 'c1',
			interpreterPath: '/a/bin/python',
			qiimeStatus: 'ready',
		});
		selectCandidate(state, 'c2');
		assert.strictEqual(state.selectedCandidateId, 'c2');
		assert.strictEqual(state.interpreterPath, '/b/bin/python');
		assert.strictEqual(state.qiimeStatus, 'unknown');
	});

	test('buildSetupWizardInterpreterCandidates orders sources correctly', () => {
		const candidates = buildSetupWizardInterpreterCandidates({
			configuredInterpreterPath: '/configured/bin/python',
			activePythonInterpreterPath: '/active/bin/python',
		});
		assert.deepStrictEqual(candidates.map((candidate) => candidate.label), [
			'Configured q2lsp interpreter',
			'Active VS Code: Python interpreter',
			'python3 from PATH',
			'python from PATH',
		]);
	});

	test('buildManagerInstallCommand builds commands for valid managers only', () => {
		assert.strictEqual(buildManagerInstallCommand('pixi'), 'curl -fsSL https://pixi.sh/install.sh | sh');
		assert.ok(buildManagerInstallCommand('conda')?.includes('Miniconda3-latest-'));
		assert.strictEqual(buildManagerInstallCommand('manual'), undefined);
		assert.strictEqual(buildManagerInstallCommand('$(touch owned)'), undefined);
	});

	test('buildQ2lspInstallCommand prefers explicit interpreter for existing route', () => {
		assert.strictEqual(
			buildQ2lspInstallCommand('existing', 'conda', 'metadata-env', '/existing qiime/bin/python'),
			"'/existing qiime/bin/python' -m pip install -U q2lsp"
		);
		assert.strictEqual(
			buildQ2lspInstallCommand('new', 'conda', 'metadata-env', '/existing qiime/bin/python'),
			"conda run -n 'metadata-env' python -m pip install -U q2lsp"
		);
	});

	test('apple silicon resolves to osx-64 conda subdir', () => {
		const platform = resolveQiimePlatform('darwin', 'arm64');
		assert.strictEqual(platform.id, 'osx-64');
		assert.strictEqual(platform.condaSubdir, 'osx-64');
	});

	test('fallback qiime environments include platform-specific files', () => {
		const platform = resolveQiimePlatform('linux', 'x64');
		const environments = buildFallbackQiimeEnvironments(platform);
		assert.ok(environments.some((environment) => environment.fileName.endsWith('linux-conda.yml')));
		assert.ok(environments.some((environment) => environment.distribution === 'amplicon'));
		assert.ok(environments.some((environment) => environment.distribution === 'moshpit'));
		assert.ok(environments.some((environment) => environment.distribution === 'pathogenome'));
		assert.ok(environments.some((environment) => environment.distribution === 'tiny'));
		assert.ok(environments.some((environment) => environment.version === '2024.10'));
	});

	test('remote qiime environments replace bundled distributions for matching versions', () => {
		const platform = resolveQiimePlatform('linux', 'x64');
		const fallbackEnvironments = buildFallbackQiimeEnvironments(platform);
		const remoteEnvironments = [
			{
				version: '2025.10',
				distribution: 'amplicon',
				platform: platform.id,
				fileName: 'qiime2-amplicon-2025.10-py310-linux-conda.yml',
				url: 'https://example.test/amplicon.yml',
				environmentName: 'qiime2-amplicon-2025.10',
			},
			{
				version: '2025.10',
				distribution: 'metagenome',
				platform: platform.id,
				fileName: 'qiime2-metagenome-2025.10-py310-linux-conda.yml',
				url: 'https://example.test/metagenome.yml',
				environmentName: 'qiime2-metagenome-2025.10',
			},
		];

		const mergedEnvironments = mergeQiimeEnvironments(fallbackEnvironments, remoteEnvironments);
		const merged2025Distributions = mergedEnvironments
			.filter((environment) => environment.version === '2025.10' && environment.platform === platform.id)
			.map((environment) => environment.distribution)
			.sort();

		assert.deepStrictEqual(merged2025Distributions, ['amplicon', 'metagenome']);
		assert.ok(mergedEnvironments.some((environment) => environment.version === '2025.7'));
	});

	test('remote qiime environment paths accept files without version naming assumptions', () => {
		const environment = parseQiimeEnvironmentPath(
			'2025.10/qiime2/released/rachis-qiime2-linux-64-conda.yml'
		);
		assert.strictEqual(environment?.fileName, 'rachis-qiime2-linux-64-conda.yml');
		assert.strictEqual(environment?.version, '2025.10');
	});

	test('remote qiime environment paths accept version-matched legacy distributions', () => {
		const environment = parseQiimeEnvironmentPath(
			'2025.10/metagenome/released/qiime2-metagenome-2025.10-py310-linux-conda.yml'
		);
		assert.strictEqual(environment?.distribution, 'metagenome');
		assert.strictEqual(environment.version, '2025.10');
	});

	test('synthetic qiime environments reject legacy qiime2 distribution entries', () => {
		const platform = resolveQiimePlatform('linux', 'x64');
		assert.strictEqual(buildSyntheticQiimeEnvironment('2025.10', 'qiime2', platform), undefined);
	});

	test('synthetic qiime environments use packages.qiime2.org urls', () => {
		const platform = resolveQiimePlatform('linux', 'x64');
		const environment = buildSyntheticQiimeEnvironment('2026.4', 'tiny', platform);
		assert.ok(environment?.url.startsWith('https://packages.qiime2.org/qiime2/2026.4/tiny/released/'));
	});

	test('git tree parser extracts released qiime environment files', () => {
		const environments = buildQiimeEnvironmentsFromTree([
			{ type: 'tree', path: '2026.4/qiime2/released' },
			{ type: 'blob', path: '2026.4/qiime2/released/rachis-qiime2-linux-64-conda.yml' },
			{ type: 'blob', path: '2026.4/qiime2/dev/rachis-qiime2-linux-64-conda.yml' },
			{ type: 'blob', path: '2025.10/amplicon/released/qiime2-amplicon-2025.10-py310-osx-conda.yml' },
			{ type: 'blob', path: '2025.10/amplicon/released/README.md' },
		]);

		assert.deepStrictEqual(
			environments.map((environment) => ({
				version: environment.version,
				distribution: environment.distribution,
				platform: environment.platform,
				fileName: environment.fileName,
			})),
			[
				{
					version: '2026.4',
					distribution: 'qiime2',
					platform: 'linux-64',
					fileName: 'rachis-qiime2-linux-64-conda.yml',
				},
				{
					version: '2025.10',
					distribution: 'amplicon',
					platform: 'osx-64',
					fileName: 'qiime2-amplicon-2025.10-py310-osx-conda.yml',
				},
			]
		);
	});

	test('serialized setup wizard functions behave like TypeScript helpers', () => {
		const state = makeState({
			route: 'existing',
			interpreterPath: '/env/bin/python',
			qiimeStatus: 'ready',
			q2lspStatus: 'ready',
			validatedInterpreterPath: '/env/bin/python',
			validatedTargetKey: 'existing:/env/bin/python',
		});
		const script = `${serializeWebviewScriptFunctions()}\nreturn { selectedInterpreterPath, saveEnabled, q2lspInstallCommand };`;
		const serialized = new Function(script)() as {
			selectedInterpreterPath: (state: WizardState) => string;
			saveEnabled: (state: WizardState) => boolean;
			q2lspInstallCommand: (state: WizardState) => string;
		};

		assert.strictEqual(serialized.selectedInterpreterPath(state), selectedInterpreterPath(state));
		assert.strictEqual(serialized.saveEnabled(state), saveEnabled(state));
		assert.strictEqual(serialized.q2lspInstallCommand(state), q2lspInstallCommand(state));
	});

	test('setup wizard HTML contains required accessibility and action elements', () => {
		const html = buildSetupWizardHtml({ nonce: 'test-nonce-123' });
		const elementById = (id: string): { tag: string; attributes: Map<string, string | true> } => {
			const elementPattern = /<([a-z][a-z0-9-]*)(\s[^>]*)?>/gi;
			let match: RegExpExecArray | null;
			while ((match = elementPattern.exec(html)) !== null) {
				const attributes = parseAttributes(match[2] ?? '');
				if (attributes.get('id') === id) {
					return { tag: match[1], attributes };
				}
			}
			assert.fail(`missing element id: ${id}`);
		};
		const elementsByAttribute = (name: string, value?: string): Array<{ tag: string; attributes: Map<string, string | true> }> => {
			const elements: Array<{ tag: string; attributes: Map<string, string | true> }> = [];
			const elementPattern = /<([a-z][a-z0-9-]*)(\s[^>]*)?>/gi;
			let match: RegExpExecArray | null;
			while ((match = elementPattern.exec(html)) !== null) {
				const attributes = parseAttributes(match[2] ?? '');
				if (attributes.has(name) && (value === undefined || attributes.get(name) === value)) {
					elements.push({ tag: match[1], attributes });
				}
			}
			return elements;
		};
		const assertHidden = (id: string): void => assert.strictEqual(elementById(id).attributes.has('hidden'), true, `expected #${id} hidden`);
		const assertVisible = (id: string): void => assert.strictEqual(elementById(id).attributes.has('hidden'), false, `expected #${id} visible`);

		for (const id of [
			'globalStatus',
			'routeScreen',
			'checklistPanel',
			'checklist',
			'existingRoute',
			'newRoute',
			'q2lspPanel',
			'candidateList',
			'managerCards',
			'versionSelect',
			'distributionSelect',
			'environmentUrlSelect',
			'qiimeCommandBox',
			'submittedTarget',
			'managerMissing',
			'metadataError',
			'saveExistingInterpreterPath',
			'saveInterpreterPathAction',
			'createEnvironmentAction',
		]) {
			elementById(id);
		}
		assert.strictEqual(elementById('globalStatus').attributes.get('role'), 'status');
		assert.strictEqual(elementById('globalStatus').attributes.get('aria-live'), 'polite');
		assert.ok(elementsByAttribute('data-command', 'validateEnvironment').length > 0);
		assert.ok(elementsByAttribute('data-command', 'validateQ2lsp').length > 0);
		assert.ok(elementsByAttribute('data-command', 'saveInterpreterPath').length > 0);
		assert.ok(elementsByAttribute('data-command', 'createQiimeEnvironment').length > 0);
		assert.ok(elementsByAttribute('data-route', 'existing').length > 0);
		assert.ok(elementsByAttribute('data-route', 'new').length > 0);

		assertVisible('routeScreen');
		assertHidden('existingRoute');
		assertHidden('newRoute');
		assertHidden('q2lspPanel');
		assertVisible('candidateList');
		assertVisible('managerCards');
		assertHidden('submittedTarget');
		assertVisible('managerMissing');
		assertHidden('metadataError');
		assert.strictEqual(elementById('saveExistingInterpreterPath').attributes.has('disabled'), true);
		assert.strictEqual(elementById('saveInterpreterPathAction').attributes.has('disabled'), true);
		assert.strictEqual(elementById('environmentUrlSelect').attributes.has('disabled'), true);
		assert.strictEqual(elementById('createEnvironmentAction').attributes.has('disabled'), false);
	});
});

const parseAttributes = (source: string): Map<string, string | true> => {
	const attributes = new Map<string, string | true>();
	const attributePattern = /([:\w-]+)(?:\s*=\s*("([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
	let match: RegExpExecArray | null;
	while ((match = attributePattern.exec(source)) !== null) {
		attributes.set(match[1], match[3] ?? match[4] ?? match[5] ?? true);
	}
	return attributes;
};
