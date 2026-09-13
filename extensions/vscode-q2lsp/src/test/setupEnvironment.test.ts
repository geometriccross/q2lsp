import * as assert from 'assert';
import { mkdtemp, readFile, rm, writeFile } from 'fs/promises';
import { tmpdir } from 'os';
import * as path from 'path';
import { createQiimeEnvironment, resolveEnvironmentInterpreter, type SetupTools } from '../setupWizard/environment';
import { buildQiimeEnvironmentsFromTree } from '../setupWizard/qiimeRemote';
import {
	buildFallbackQiimeEnvironments,
	buildSyntheticQiimeEnvironment,
	mergeQiimeEnvironments,
	parseQiimeEnvironmentPath,
	resolveQiimePlatform,
} from '../setupWizard/qiimeMetadata';
import type { QiimeEnvironmentOption } from '../setupWizard/qiimeConstants';

suite('q2lsp setup environment tools', () => {
	const environment: QiimeEnvironmentOption = {
		version: '2026.4', distribution: 'tiny', platform: 'osx-64',
		fileName: 'qiime2-tiny-2026.4-osx-64-conda.yml',
		url: 'https://packages.qiime2.org/qiime2/2026.4/tiny/released/qiime2-tiny-2026.4-osx-64-conda.yml',
		environmentName: 'qiime2-tiny-2026.4',
	};

	test('Conda resolves the installed environment without activating it', async () => {
		const calls: Array<Parameters<SetupTools['run']>> = [];
		const prefix = `/conda/envs/${environment.environmentName}`;
		const run: SetupTools['run'] = async (...args) => {
			calls.push(args);
			assert.notStrictEqual(args[1][0], 'run', 'path lookup must not execute activation scripts');
			return JSON.stringify({ envs: ['/conda', prefix] });
		};
		const platform = resolveQiimePlatform('darwin', 'arm64');
		assert.strictEqual(platform.id, 'osx-64');
		const interpreter = await createQiimeEnvironment(run, 'conda', environment, platform);
		assert.strictEqual(interpreter, path.join(prefix, 'bin', 'python'));
		assert.deepStrictEqual(calls[0].slice(0, 2), [
			'conda', ['env', 'create', '--name', environment.environmentName, '--file', environment.url],
		]);
		assert.strictEqual(calls[0][2]?.env?.CONDA_SUBDIR, 'osx-64');
		assert.deepStrictEqual(calls[1][1], ['env', 'list', '--json']);
	});

	test('unsafe environment metadata cannot reach a process', async () => {
		const run: SetupTools['run'] = async () => assert.fail('must reject before execution');
		for (const patch of [
			{ url: 'https://example.com/environment.yml' },
			{ url: 'http://packages.qiime2.org/qiime2/env.yml' },
			{ environmentName: 'env; echo unsafe' },
			{ environmentName: '--prefix' },
		]) {
			await assert.rejects(createQiimeEnvironment(run, 'conda', { ...environment, ...patch }, { id: 'osx-64', label: 'macOS' }));
		}
	});

	for (const existingManifest of [undefined, 'pixi.toml', 'pyproject.toml']) {
		test(`Pixi configures and resolves default without activation (${existingManifest ?? 'new project'})`, async () => {
			const originalFetch = globalThis.fetch;
			const project = await mkdtemp(path.join(tmpdir(), 'q2lsp-pixi-test-'));
			const prefix = path.join(project, 'detached environments', 'default');
			const calls: Array<Parameters<SetupTools['run']>> = [];
			let manifest = '';
			globalThis.fetch = async () => new Response('name: qiime\ndependencies: [python]\n');
			const run: SetupTools['run'] = async (...args) => {
				calls.push(args);
				if (args[1][0] === 'import') {
					manifest = args[1][3];
					assert.ok((await readFile(manifest, 'utf8')).includes('dependencies: [python]'));
				}
				assert.notStrictEqual(args[1][0], 'run', 'path lookup must not execute activation scripts');
				return JSON.stringify({ environments_info: [
					{ name: environment.environmentName, prefix: path.join(project, '.pixi', 'envs', environment.environmentName) },
					{ name: 'default', prefix },
				] });
			};
			try {
				if (existingManifest) {
					await writeFile(path.join(project, existingManifest), '');
				}
				const interpreter = await createQiimeEnvironment(run, 'pixi', environment, { id: 'osx-64', label: 'macOS' }, project);
				assert.strictEqual(interpreter, path.join(prefix, 'bin', 'python'));
				assert.deepStrictEqual(calls.map((call) => call[1][0]), [
					...(existingManifest ? [] : ['init']), 'import', 'workspace', 'install', 'info',
				]);
				assert.ok(calls.every((call) => call[2]?.cwd === project));
				if (!existingManifest) {
					assert.deepStrictEqual(calls.shift()![1], ['init', '-p', 'osx-64']);
				}
				assert.deepStrictEqual(calls[0][1].slice(4), ['-e', 'default', '-f', environment.environmentName, '-p', 'osx-64']);
				assert.deepStrictEqual(calls[1][1], [
					'workspace', 'environment', 'add', 'default', '--feature', environment.environmentName, '--no-default-feature', '--force',
				]);
				assert.deepStrictEqual(calls[2][1], ['install', '-e', 'default']);
				assert.deepStrictEqual(calls[3][1], ['info', '--json']);
				await assert.rejects(readFile(manifest));
			} finally {
				globalThis.fetch = originalFetch;
				await rm(project, { recursive: true, force: true });
			}
		});
	}

	test('missing, relative, or ambiguous environment prefixes fail instead of guessing a Python path', async () => {
		for (const info of [
			{},
			{ environments_info: [{ name: 'other', prefix: '/other' }] },
			{ environments_info: [{ name: environment.environmentName, prefix: '../relative' }] },
			{ environments_info: [
				{ name: environment.environmentName, prefix: '/first' },
				{ name: environment.environmentName, prefix: '/second' },
			] },
		]) {
			await assert.rejects(
				resolveEnvironmentInterpreter(async () => JSON.stringify(info), 'pixi', environment.environmentName, '/project'),
				/Could not locate the pixi environment/,
			);
		}
		await assert.rejects(resolveEnvironmentInterpreter(async () => JSON.stringify({ envs: [
			`/first/${environment.environmentName}`, `/second/${environment.environmentName}`,
		] }), 'conda', environment.environmentName), /Could not locate the conda environment/);
	});

	test('remote tree parsing uses released, platform-specific files and newest versions first', () => {
		const environments = buildQiimeEnvironmentsFromTree([
			{ type: 'blob', path: '2025.10/amplicon/released/qiime2-amplicon-2025.10-py310-osx-conda.yml' },
			{ type: 'tree', path: '2026.4/qiime2/released' },
			{ type: 'blob', path: '2026.4/qiime2/released/rachis-qiime2-linux-64-conda.yml' },
			{ type: 'blob', path: '2026.4/qiime2/dev/rachis-qiime2-linux-64-conda.yml' },
			{ type: 'blob', path: '2025.10/amplicon/released/README.md' },
		]);
		assert.deepStrictEqual(environments.map((env) => [env.version, env.distribution, env.platform]), [
			['2026.4', 'qiime2', 'linux-64'], ['2025.10', 'amplicon', 'osx-64'],
		]);
		assert.ok(environments[0].url.startsWith('https://raw.githubusercontent.com/qiime2/distributions/'));
	});

	test('environment paths accept released files without legacy naming assumptions', () => {
		const current = parseQiimeEnvironmentPath('2025.10/qiime2/released/rachis-qiime2-linux-64-conda.yml');
		assert.strictEqual(current?.fileName, 'rachis-qiime2-linux-64-conda.yml');
		assert.strictEqual(current?.version, '2025.10');
		const legacy = parseQiimeEnvironmentPath('2025.10/metagenome/released/qiime2-metagenome-2025.10-py310-linux-conda.yml');
		assert.strictEqual(legacy?.distribution, 'metagenome');
	});

	test('remote environments replace fallback distributions for the same version and platform', () => {
		const platform = resolveQiimePlatform('linux', 'x64');
		const fallback = buildFallbackQiimeEnvironments(platform);
		assert.ok(fallback.some((env) => env.fileName.endsWith('linux-conda.yml')));
		for (const distribution of ['amplicon', 'moshpit', 'pathogenome', 'tiny']) {
			assert.ok(fallback.some((env) => env.distribution === distribution));
		}
		const remote = ['amplicon', 'metagenome'].map((distribution) => ({
			...environment, version: '2025.10', distribution, platform: platform.id,
		}));
		const merged = mergeQiimeEnvironments(fallback, remote);
		assert.deepStrictEqual(merged.filter((env) => env.version === '2025.10').map((env) => env.distribution), ['amplicon', 'metagenome']);
		assert.ok(merged.some((env) => env.version === '2025.7'));
	});

	test('synthetic environments retain package URLs and reject legacy qiime2 distributions', () => {
		const platform = resolveQiimePlatform('linux', 'x64');
		assert.strictEqual(buildSyntheticQiimeEnvironment('2025.10', 'qiime2', platform), undefined);
		assert.ok(buildSyntheticQiimeEnvironment('2026.4', 'tiny', platform)?.url.startsWith('https://packages.qiime2.org/qiime2/2026.4/tiny/released/'));
	});
});
