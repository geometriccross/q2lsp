import {
	QIIME_DISTRIBUTIONS,
	QIIME_VERSIONS,
	type QiimeEnvironmentOption,
	type QiimePlatform,
} from './qiimeConstants';

export const buildSyntheticQiimeEnvironment = (
	version: string,
	distribution: string,
	platform: QiimePlatform
): QiimeEnvironmentOption | undefined => {
	if (isRachisQiimeVersion(version)) {
		const fileName = `rachis-${distribution}-${platform.id}-conda.yml`;
		return {
			version,
			distribution,
			platform: platform.id,
			fileName,
			url: `https://raw.githubusercontent.com/qiime2/distributions/refs/heads/dev/${version}/${distribution}/released/${fileName}`,
			environmentName: fileName.replace(/-(linux-64|osx-64|osx-arm64|linux|osx)-conda\.yml$/, ''),
		};
	}

	if (distribution === 'qiime2') {
		return undefined;
	}
	const legacyPlatform = platform.id === 'linux-64' ? 'linux' : 'osx';
	const fileName = `qiime2-${distribution}-${version}-py310-${legacyPlatform}-conda.yml`;
	return {
		version,
		distribution,
		platform: platform.id,
		fileName,
		url: `https://raw.githubusercontent.com/qiime2/distributions/refs/heads/dev/${version}/${distribution}/released/${fileName}`,
		environmentName: `qiime2-${distribution}-${version}`,
	};
};

export const parseQiimeEnvironmentPath = (entryPath: string): QiimeEnvironmentOption | undefined => {
	const match = /^(?<version>\d{4}\.\d+)\/(?<distribution>[^/]+)\/released\/(?<fileName>.+-(?<platform>linux-64|osx-64|osx-arm64|linux|osx)-conda\.yml)$/.exec(entryPath);
	const groups = match?.groups;
	if (!groups) {
		return undefined;
	}
	const platform = normalizeQiimePlatformId(groups.platform);
	const fileMetadata = parseQiimeEnvironmentFileName(groups.fileName);
	if (!fileMetadata) {
		return undefined;
	}
	if (fileMetadata.platform !== platform || fileMetadata.distribution !== groups.distribution) {
		return undefined;
	}
	if (fileMetadata.kind === 'rachis' && !isRachisQiimeVersion(groups.version)) {
		return undefined;
	}
	if (fileMetadata.kind === 'legacy') {
		if (isRachisQiimeVersion(groups.version) || fileMetadata.version !== groups.version) {
			return undefined;
		}
	}

	return {
		version: groups.version,
		distribution: groups.distribution,
		platform,
		fileName: groups.fileName,
		url: `https://raw.githubusercontent.com/qiime2/distributions/refs/heads/dev/${entryPath}`,
		environmentName: groups.fileName.replace(/-(linux-64|osx-64|osx-arm64|linux|osx)-conda\.yml$/, ''),
	};
};

type QiimeEnvironmentFileMetadata =
	| {
		kind: 'rachis';
		distribution: string;
		platform: string;
	}
	| {
		kind: 'legacy';
		distribution: string;
		version: string;
		platform: string;
	};

const parseQiimeEnvironmentFileName = (fileName: string): QiimeEnvironmentFileMetadata | undefined => {
	const rachisMatch = /^rachis-(?<distribution>.+)-(?<platform>linux-64|osx-64|osx-arm64)-conda\.yml$/.exec(fileName);
	if (rachisMatch?.groups) {
		return {
			kind: 'rachis',
			distribution: rachisMatch.groups.distribution,
			platform: normalizeQiimePlatformId(rachisMatch.groups.platform),
		};
	}

	const legacyMatch = /^qiime2-(?<distribution>.+)-(?<version>\d{4}\.\d+)-py\d+-(?<platform>linux|osx)-conda\.yml$/.exec(fileName);
	if (!legacyMatch?.groups) {
		return undefined;
	}
	return {
		kind: 'legacy',
		distribution: legacyMatch.groups.distribution,
		version: legacyMatch.groups.version,
		platform: normalizeQiimePlatformId(legacyMatch.groups.platform),
	};
};

const isRachisQiimeVersion = (version: string): boolean => {
	const year = Number(version.split('.')[0]);
	return Number.isFinite(year) && year >= 2026;
};

const normalizeQiimePlatformId = (platform: string): string => {
	if (platform === 'linux') {
		return 'linux-64';
	}
	if (platform === 'osx') {
		return 'osx-64';
	}
	return platform;
};

export const compareQiimeEnvironmentOptions = (
	left: QiimeEnvironmentOption,
	right: QiimeEnvironmentOption
): number => {
	const versionComparison = right.version.localeCompare(left.version, undefined, { numeric: true });
	if (versionComparison !== 0) {
		return versionComparison;
	}
	return left.distribution.localeCompare(right.distribution);
};

export const resolveQiimePlatform = (platform: NodeJS.Platform, arch: string): QiimePlatform => {
	if (platform === 'darwin') {
		if (arch === 'arm64') {
			return { id: 'osx-64', label: 'macOS Apple Silicon using osx-64', condaSubdir: 'osx-64' };
		}
		return { id: 'osx-64', label: 'macOS Intel' };
	}
	return { id: 'linux-64', label: 'Linux / WSL' };
};

export const buildFallbackQiimeEnvironments = (platform: QiimePlatform): QiimeEnvironmentOption[] => {
	const options: QiimeEnvironmentOption[] = [];
	for (const version of QIIME_VERSIONS) {
		if (version.startsWith('2026.')) {
			const fileName = `rachis-qiime2-${platform.id}-conda.yml`;
			options.push({
				version,
				distribution: 'qiime2',
				platform: platform.id,
				fileName,
				url: `https://raw.githubusercontent.com/qiime2/distributions/refs/heads/dev/${version}/qiime2/released/${fileName}`,
				environmentName: fileName.replace(/-(linux-64|osx-64|osx-arm64|linux|osx)-conda\.yml$/, ''),
			});
			continue;
		}

		for (const distribution of QIIME_DISTRIBUTIONS) {
			const legacyPlatform = platform.id === 'linux-64' ? 'linux' : 'osx';
			const fileName = `qiime2-${distribution}-${version}-py310-${legacyPlatform}-conda.yml`;
			options.push({
				version,
				distribution,
				platform: platform.id,
				fileName,
				url: `https://raw.githubusercontent.com/qiime2/distributions/refs/heads/dev/${version}/${distribution}/released/${fileName}`,
				environmentName: `qiime2-${distribution}-${version}`,
			});
		}
	}
	return options;
};

export const mergeQiimeEnvironments = (
	fallbackEnvironments: QiimeEnvironmentOption[],
	remoteEnvironments: QiimeEnvironmentOption[]
): QiimeEnvironmentOption[] => {
	const remoteVersionPlatforms = new Set(
		remoteEnvironments.map((environment) => formatQiimeVersionPlatformKey(environment))
	);
	const merged = new Map<string, QiimeEnvironmentOption>();
	for (const environment of fallbackEnvironments) {
		if (remoteVersionPlatforms.has(formatQiimeVersionPlatformKey(environment))) {
			continue;
		}
		merged.set(formatQiimeEnvironmentKey(environment), environment);
	}
	for (const environment of remoteEnvironments) {
		merged.set(formatQiimeEnvironmentKey(environment), environment);
	}
	return Array.from(merged.values()).sort(compareQiimeEnvironmentOptions);
};

const formatQiimeVersionPlatformKey = (environment: QiimeEnvironmentOption): string => {
	return [
		environment.version,
		environment.platform,
	].join('\0');
};

const formatQiimeEnvironmentKey = (environment: QiimeEnvironmentOption): string => {
	return [
		environment.version,
		environment.distribution,
		environment.platform,
	].join('\0');
};
