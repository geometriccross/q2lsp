import * as assert from 'assert';
import {
	QIIME_DISTRIBUTIONS,
	QIIME_VERSIONS,
	SETUP_WIZARD_FLOW_STEPS,
	SETUP_WIZARD_MANAGERS,
	buildFallbackQiimeEnvironments,
	buildSetupWizardHtml,
	buildSyntheticQiimeEnvironment,
	mergeQiimeEnvironments,
	parseQiimeEnvironmentPath,
	resolveQiimePlatform,
} from '../setupWizard';

suite('q2lsp setup wizard tests', () => {
	test('wizard html shows the setup flow steps', () => {
		const html = buildSetupWizardHtml({ nonce: 'test-nonce' });

		for (const step of SETUP_WIZARD_FLOW_STEPS) {
			assert.ok(html.includes(step.label));
		}
	});

	test('wizard html shows package managers and qiime selectors', () => {
		const html = buildSetupWizardHtml({ nonce: 'test-nonce' });

		for (const manager of SETUP_WIZARD_MANAGERS) {
			assert.ok(html.includes(manager.label));
		}
		for (const distribution of QIIME_DISTRIBUTIONS) {
			assert.ok(html.includes(distribution));
		}
		for (const version of QIIME_VERSIONS) {
			assert.ok(html.includes(version));
		}
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

	test('remote qiime environment paths reject mismatched rachis files for legacy versions', () => {
		const environment = parseQiimeEnvironmentPath(
			'2025.10/qiime2/released/rachis-qiime2-linux-64-conda.yml'
		);

		assert.strictEqual(environment, undefined);
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
});
