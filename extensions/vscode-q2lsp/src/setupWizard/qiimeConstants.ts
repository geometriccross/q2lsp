export const QIIME_DISTRIBUTIONS = ['amplicon', 'moshpit', 'pathogenome', 'tiny'] as const;

export const QIIME_VERSIONS = ['2026.4', '2026.1', '2025.10', '2025.7', '2025.4', '2024.10', '2024.5', '2024.2', '2023.9'] as const;

export type QiimePlatform = {
	id: string;
	label: string;
	condaSubdir?: string;
};

export type QiimeEnvironmentOption = {
	version: string;
	distribution: string;
	platform: string;
	fileName: string;
	url: string;
	environmentName: string;
};

export const QIIME_PACKAGES_BASE_URL = 'https://packages.qiime2.org/qiime2';
export const QIIME_DISTRIBUTIONS_TREE_URL =
	'https://api.github.com/repos/qiime2/distributions/git/trees/dev?recursive=1';
export const QIIME_QUICKSTART_URL = 'https://library.qiime2.org/quickstart/qiime2';
