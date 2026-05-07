import {
	QIIME_DISTRIBUTIONS,
	QIIME_PACKAGES_BASE_URL,
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
			url: `${QIIME_PACKAGES_BASE_URL}/${version}/${distribution}/released/${fileName}`,
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
		url: `${QIIME_PACKAGES_BASE_URL}/${version}/${distribution}/released/${fileName}`,
		environmentName: `qiime2-${distribution}-${version}`,
	};
};

export const parseQiimeEnvironmentPath = (entryPath: string): QiimeEnvironmentOption | undefined => {
	const match = /^(?<version>\d{4}\.\d+)\/(?<distribution>[^/]+)\/released\/(?<fileName>.+\.ya?ml)$/.exec(entryPath);
	const groups = match?.groups;
	if (!groups) {
		return undefined;
	}

	return {
		version: groups.version,
		distribution: groups.distribution,
		platform: inferQiimePlatformId(groups.fileName),
		fileName: groups.fileName,
		url: `${QIIME_PACKAGES_BASE_URL}/${entryPath}`,
		environmentName: formatQiimeEnvironmentName(groups.fileName),
	};
};

const isRachisQiimeVersion = (version: string): boolean => {
	const year = Number(version.split('.')[0]);
	return Number.isFinite(year) && year >= 2026;
};

export const inferQiimePlatformId = (fileName: string): string => {
	if (/(^|-)linux-64(-|\.|_)/.test(fileName) || /(^|-)linux(-|\.|_)/.test(fileName)) {
		return 'linux-64';
	}
	if (/(^|-)osx-64(-|\.|_)/.test(fileName) || /(^|-)osx(-|\.|_)/.test(fileName)) {
		return 'osx-64';
	}
	if (/(^|-)osx-arm64(-|\.|_)/.test(fileName)) {
		return 'osx-arm64';
	}
	if (fileName.includes('ubuntu-latest')) {
		return 'ubuntu-latest';
	}
	if (fileName.includes('macos-latest')) {
		return 'macos-latest';
	}
	return 'unknown';
};

export const formatQiimeEnvironmentName = (fileName: string): string => {
	return fileName
		.replace(/-conda\.ya?ml$/, '')
		.replace(/\.ya?ml$/, '');
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
				url: `${QIIME_PACKAGES_BASE_URL}/${version}/qiime2/released/${fileName}`,
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
				url: `${QIIME_PACKAGES_BASE_URL}/${version}/${distribution}/released/${fileName}`,
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
