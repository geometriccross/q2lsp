import * as vscode from 'vscode';
import {
	QIIME_DISTRIBUTIONS_TREE_URL,
	type QiimeEnvironmentOption,
} from './qiimeConstants';
import {
	compareQiimeEnvironmentOptions,
	formatQiimeEnvironmentName,
	inferQiimePlatformId,
} from './qiimeMetadata';

export const refreshQiimeManifest = async (webview: vscode.Webview): Promise<void> => {
	const remoteEnvironments = await fetchQiimeEnvironmentsFromTree();
	if (remoteEnvironments.length > 0) {
		await webview.postMessage({
			type: 'qiimeManifest',
			environments: remoteEnvironments,
		});
		return;
	}

	await webview.postMessage({
		type: 'qiimeManifest',
		environments: [],
	});
};

const fetchQiimeEnvironmentsFromTree = async (): Promise<QiimeEnvironmentOption[]> => {
	try {
		return buildQiimeEnvironmentsFromTree(await fetchGitHubTree());
	} catch {
		return [];
	}
};

export const buildQiimeEnvironmentsFromTree = (entries: GitHubTreeEntry[]): QiimeEnvironmentOption[] => {
	return entries
		.filter((entry) => entry.type === 'blob')
		.map((entry) => buildQiimeEnvironmentFromTreeEntry(entry))
		.filter((environment): environment is QiimeEnvironmentOption => environment !== undefined)
		.sort(compareQiimeEnvironmentOptions);
};

type GitHubTreeEntry = {
	path?: unknown;
	type?: unknown;
};

const fetchGitHubTree = async (): Promise<GitHubTreeEntry[]> => {
	const response = await fetch(QIIME_DISTRIBUTIONS_TREE_URL, {
		headers: {
			Accept: 'application/vnd.github+json',
		},
	});
	if (!response.ok) {
		return [];
	}
	const parsed = (await response.json()) as unknown;
	if (!isGitHubTreeResponse(parsed)) {
		return [];
	}
	return parsed.tree;
};

const isGitHubTreeResponse = (value: unknown): value is { tree: GitHubTreeEntry[] } => {
	return typeof value === 'object'
		&& value !== null
		&& Array.isArray((value as { tree?: unknown }).tree);
};

const buildQiimeEnvironmentFromTreeEntry = (
	entry: GitHubTreeEntry
): QiimeEnvironmentOption | undefined => {
	if (typeof entry.path !== 'string') {
		return undefined;
	}
	const match = /^(?<version>\d{4}\.\d+)\/(?<distribution>[^/]+)\/released\/(?<fileName>[^/]+\.ya?ml)$/.exec(entry.path);
	const groups = match?.groups;
	if (!groups) {
		return undefined;
	}
	return {
		version: groups.version,
		distribution: groups.distribution,
		platform: inferQiimePlatformId(groups.fileName),
		fileName: groups.fileName,
		url: `https://raw.githubusercontent.com/qiime2/distributions/refs/heads/dev/${entry.path}`,
		environmentName: formatQiimeEnvironmentName(groups.fileName),
	};
};
