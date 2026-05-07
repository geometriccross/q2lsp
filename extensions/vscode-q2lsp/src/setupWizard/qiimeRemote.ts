import * as vscode from 'vscode';
import {
	QIIME_MANIFEST_CONTENTS_URL,
	QIIME_MANIFEST_TREE_URL,
	QIIME_PACKAGES_BASE_URL,
	type QiimeEnvironmentOption,
	type QiimePlatform,
} from './qiimeConstants';
import {
	buildFallbackQiimeEnvironments,
	buildSyntheticQiimeEnvironment,
	compareQiimeEnvironmentOptions,
	mergeQiimeEnvironments,
	parseQiimeEnvironmentPath,
} from './qiimeMetadata';

export const refreshQiimeManifest = async (webview: vscode.Webview, platform: QiimePlatform): Promise<void> => {
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
