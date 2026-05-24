import * as assert from 'assert';
import {
	SETUP_WIZARD_FLOW_STEPS,
	SETUP_WIZARD_MANAGERS,
	buildFallbackQiimeEnvironments,
	buildQiimeEnvironmentsFromTree,
	buildSetupWizardHtml,
	buildSyntheticQiimeEnvironment,
	mergeQiimeEnvironments,
	parseQiimeEnvironmentPath,
	resolveQiimePlatform,
} from '../setupWizard/index';

suite('q2lsp setup wizard tests', () => {
	test('wizard html shows the setup flow steps', () => {
		const html = buildSetupWizardHtml({ nonce: 'test-nonce' });

		for (const [index, step] of SETUP_WIZARD_FLOW_STEPS.entries()) {
			assert.ok(html.includes(`<span class="step-index">${index + 1}</span>`));
			assert.ok(html.includes(step.label.replace(/^\d\s/, '')));
		}
	});

	test('wizard html shows package managers and empty qiime selectors before fetch', () => {
		const html = buildSetupWizardHtml({ nonce: 'test-nonce' });

		for (const manager of SETUP_WIZARD_MANAGERS) {
			assert.ok(html.includes(manager.label));
		}
		const versionSelect = html.match(/<select id="versionSelect">(?<options>[\s\S]*?)<\/select>/)
			?.groups?.options.trim() ?? '';
		const distributionSelect = html.match(/<select id="distributionSelect">(?<options>[\s\S]*?)<\/select>/)
			?.groups?.options.trim() ?? '';
		const environmentUrlSelect = html.match(/<select id="environmentUrlSelect">(?<options>[\s\S]*?)<\/select>/)
			?.groups?.options.trim() ?? '';

		assert.strictEqual(versionSelect, '');
		assert.strictEqual(distributionSelect, '');
		assert.strictEqual(environmentUrlSelect, '');
	});

	test('conda manager installs miniconda from the terminal', () => {
		const condaManager = SETUP_WIZARD_MANAGERS.find((manager) => manager.id === 'conda');
		const html = buildSetupWizardHtml({ nonce: 'test-nonce' });

		assert.ok(condaManager);
		assert.ok(condaManager?.command.startsWith('curl -fsSLo Miniconda3.sh '));
		assert.ok(condaManager.command.includes('https://repo.anaconda.com/miniconda/Miniconda3-latest-'));
		assert.ok(condaManager.command.includes(' && bash Miniconda3.sh'));
		assert.ok(html.includes('Conda / Miniconda'));
		assert.ok(html.includes('Install Miniconda in Terminal'));
		assert.ok(!html.includes('Miniforge'));
	});

	test('wizard html starts with distributions for the initial version only', () => {
		const platform = resolveQiimePlatform('linux', 'x64');
		const html = buildSetupWizardHtml({
			nonce: 'test-nonce',
			platform,
			environments: [
				{
					version: '2026.4',
					distribution: 'qiime2',
					platform: platform.id,
					fileName: 'rachis-qiime2-linux-64-conda.yml',
					url: 'https://example.test/qiime2.yml',
					environmentName: 'rachis-qiime2',
				},
				{
					version: '2025.10',
					distribution: 'amplicon',
					platform: platform.id,
					fileName: 'qiime2-amplicon-2025.10-py310-linux-conda.yml',
					url: 'https://example.test/amplicon.yml',
					environmentName: 'qiime2-amplicon-2025.10',
				},
			],
		});
		const distributionSelect = html.match(/<select id="distributionSelect">(?<options>[\s\S]*?)<\/select>/)
			?.groups?.options ?? '';

		assert.ok(distributionSelect.includes('qiime2'));
		assert.ok(!distributionSelect.includes('amplicon'));
	});

	test('wizard html shows selectable environment file urls for qiime install', () => {
		const platform = resolveQiimePlatform('linux', 'x64');
		const html = buildSetupWizardHtml({
			nonce: 'test-nonce',
			platform,
			environments: [
				{
					version: '2026.4',
					distribution: 'tiny',
					platform: 'linux-64',
					fileName: 'rachis-tiny-linux-64-conda.yml',
					url: 'https://raw.githubusercontent.com/qiime2/distributions/refs/heads/dev/2026.4/tiny/released/rachis-tiny-linux-64-conda.yml',
					environmentName: 'rachis-tiny',
				},
			],
		});

		assert.ok(html.includes('Environment file URL'));
		assert.ok(html.includes('id="environmentUrlSelect"'));
		assert.ok(html.includes('https://raw.githubusercontent.com/qiime2/distributions/refs/heads/dev/2026.4/tiny/released/rachis-tiny-linux-64-conda.yml'));
		assert.ok(html.includes('>rachis-tiny-linux-64-conda.yml</option>'));
	});

	test('wizard html shows pixi commands for the current workspace', () => {
		const html = buildSetupWizardHtml({
			nonce: 'test-nonce',
			environments: [
				{
					version: '2026.4',
					distribution: 'qiime2',
					platform: 'linux-64',
					fileName: 'rachis-qiime2-linux-64-conda.yml',
					url: 'https://raw.githubusercontent.com/qiime2/distributions/refs/heads/dev/2026.4/qiime2/released/rachis-qiime2-linux-64-conda.yml',
					environmentName: 'rachis-qiime2',
				},
			],
		});

		assert.ok(html.includes('https://raw.githubusercontent.com/qiime2/distributions/refs/heads/dev/2026.4/qiime2/released/rachis-qiime2-linux-64-conda.yml'));
		assert.ok(html.includes('pixi init && pixi import --format conda-env'));
		assert.ok(html.includes("' -e ' + pixiEnvironmentName() + ' && pixi install'"));
		assert.ok(!html.includes('--format pyproject'));
		assert.ok(html.includes('pixi run python -m pip install -U q2lsp'));
		assert.ok(!html.includes('mkdir -p .qiime2'));
		assert.ok(!html.includes('cd .qiime2'));
	});

	test('wizard html omits the log action', () => {
		const html = buildSetupWizardHtml({ nonce: 'test-nonce' });

		assert.ok(!html.includes('Show q2lsp Log'));
		assert.ok(!html.includes('showQ2lspLog'));
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

	test('synthetic qiime environments use packages.qiime2.org urls', () => {
		const platform = resolveQiimePlatform('linux', 'x64');
		const environment = buildSyntheticQiimeEnvironment('2026.4', 'tiny', platform);

		assert.ok(environment?.url.startsWith('https://packages.qiime2.org/qiime2/2026.4/tiny/released/'));
	});
});
