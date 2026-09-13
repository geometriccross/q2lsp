import { execFile, type ExecFileOptionsWithStringEncoding } from 'child_process';
import { existsSync } from 'fs';
import { mkdtemp, rm, writeFile } from 'fs/promises';
import { tmpdir } from 'os';
import * as path from 'path';
import type * as vscode from 'vscode';
import {
	buildInterpreterValidationSnippet,
	parseInterpreterValidationStdout,
	type InterpreterValidationDetails,
} from '../interpreter';
import { isAbsolutePath } from '../interpreterPath';
import { type QiimeEnvironmentOption, type QiimePlatform } from './qiimeConstants';
import { fetchQiimeEnvironments } from './qiimeRemote';

export type SetupTools = {
	run: (file: string, args: string[], options?: ExecFileOptionsWithStringEncoding) => Promise<string>;
	check: (interpreterPath: string) => Promise<InterpreterValidationDetails>;
	environments: () => Promise<QiimeEnvironmentOption[]>;
};

export const createSetupTools = (output: vscode.OutputChannel): SetupTools => {
	const run: SetupTools['run'] = (file, args, options) => new Promise((resolve, reject) => {
		output.appendLine(`> ${file} ${args.join(' ')}`);
		const child = execFile(file, args, {
			encoding: 'utf8',
			timeout: 10000,
			maxBuffer: 16 * 1024 * 1024,
			...options,
		}, (error, stdout, stderr) => {
			if (error) {
				reject(new Error((stderr.trim() || error.message).slice(0, 300)));
			} else {
				resolve(stdout);
			}
		});
		child.stdout?.on('data', (data: string) => output.append(data));
		child.stderr?.on('data', (data: string) => output.append(data));
	});
	return {
		run,
		environments: fetchQiimeEnvironments,
		check: async (interpreterPath) => {
			const stdout = await run(interpreterPath, [
				'-c', buildInterpreterValidationSnippet(['qiime2', 'q2cli', 'q2lsp']),
			]);
			const details = parseInterpreterValidationStdout(stdout);
			if (!details || !isAbsolutePath(details.executable)) {
				throw new Error('Python did not report a valid executable path. Choose another interpreter.');
			}
			return details;
		},
	};
};

export const resolveEnvironmentInterpreter = async (
	run: SetupTools['run'],
	manager: 'conda' | 'pixi',
	environmentName: string,
	cwd?: string,
): Promise<string> => {
	// Manager `run` commands activate QIIME's shell-completion hooks. Metadata
	// gives us the prefix without starting QIIME or assuming an install location.
	const info = JSON.parse(await run(
		manager, manager === 'pixi' ? ['info', '--json'] : ['env', 'list', '--json'],
		{ encoding: 'utf8', cwd },
	)) as {
		environments_info?: Array<{ name?: unknown; prefix?: unknown }>;
		envs?: unknown[];
	} | null;
	const prefixes = manager === 'pixi'
		? (Array.isArray(info?.environments_info) ? info.environments_info : [])
			.filter((environment) => environment?.name === environmentName).map((environment) => environment.prefix)
		: (Array.isArray(info?.envs) ? info.envs : [])
			.filter((prefix) => typeof prefix === 'string' && path.basename(prefix) === environmentName);
	const [prefix] = prefixes;
	if (prefixes.length !== 1 || typeof prefix !== 'string' || !path.isAbsolute(prefix)) {
		throw new Error(`Could not locate the ${manager} environment ${environmentName}. Browse to its Python interpreter instead.`);
	}
	return path.join(prefix, 'bin', 'python');
};

export const createQiimeEnvironment = async (
	run: SetupTools['run'],
	manager: 'conda' | 'pixi',
	environment: QiimeEnvironmentOption,
	platform: QiimePlatform,
	cwd?: string,
): Promise<string> => {
	const { environmentName, url } = environment;
	const parsed = new URL(url);
	const allowedUrl = parsed.protocol === 'https:' && /\.ya?ml$/.test(parsed.pathname) && (
		(parsed.hostname === 'packages.qiime2.org' && parsed.pathname.startsWith('/qiime2/')) ||
		(parsed.hostname === 'raw.githubusercontent.com' && parsed.pathname.startsWith('/qiime2/distributions/refs/heads/dev/'))
	);
	if (!allowedUrl || !/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(environmentName)) {
		throw new Error('Invalid QIIME 2 environment metadata. Use the official QIIME 2 Quickstart.');
	}

	if (manager === 'conda') {
		await run('conda', ['env', 'create', '--name', environmentName, '--file', url], {
			encoding: 'utf8',
			timeout: 3600000,
			env: { ...process.env, ...(platform.condaSubdir ? { CONDA_SUBDIR: platform.condaSubdir } : {}) },
		});
		return resolveEnvironmentInterpreter(run, 'conda', environmentName);
	}

	if (!cwd) {
		throw new Error('Choose a folder for the Pixi project.');
	}
	// Pixi imports a local file; keep the downloaded manifest out of the project.
	const response = await fetch(url, { signal: AbortSignal.timeout(30000) });
	if (!response.ok) {
		throw new Error(`Could not download the QIIME 2 environment file (${response.status}).`);
	}
	const directory = await mkdtemp(path.join(tmpdir(), 'q2lsp-setup-'));
	const options: ExecFileOptionsWithStringEncoding = { encoding: 'utf8', cwd, timeout: 3600000 };
	try {
		const file = path.join(directory, 'environment.yml');
		await writeFile(file, await response.text());
		if (!existsSync(path.join(cwd, 'pixi.toml')) && !existsSync(path.join(cwd, 'pyproject.toml'))) {
			await run('pixi', ['init', '-p', platform.id], options);
		}
		await run('pixi', ['import', '--format', 'conda-env', file, '-e', 'default', '-f', environmentName, '-p', platform.id], options);
		// The workspace's implicit default feature may target osx-arm64 while
		// QIIME targets osx-64. Use only the imported feature in this environment.
		await run('pixi', [
			'workspace', 'environment', 'add', 'default', '--feature', environmentName, '--no-default-feature', '--force',
		], options);
		await run('pixi', ['install', '-e', 'default'], options);
		return resolveEnvironmentInterpreter(run, 'pixi', 'default', cwd);
	} finally {
		await rm(directory, { recursive: true, force: true });
	}
};
