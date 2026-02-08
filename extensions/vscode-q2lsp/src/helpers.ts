import * as path from 'path';

export type InterpreterCandidateSource = 'config' | 'pythonExtension' | 'path';

export type InterpreterCandidate = {
	path: string;
	source: InterpreterCandidateSource;
};

export const DEFAULT_PATH_CANDIDATES = ['python3', 'python'] as const;
export const REQUIRED_PYTHON_MODULES = ['q2lsp', 'q2cli'] as const;
export const QIIME2_QUICKSTART_URL = 'https://library.qiime2.org/quickstart/amplicon';
export const Q2CLI_MISSING_QIIME_HINT =
	` QIIME 2 is not installed in this Python environment (missing q2cli). Install QIIME 2: ${QIIME2_QUICKSTART_URL}.`;

export type InterpreterValidationDetails = {
	missing: string[];
	executable: string;
	version: string;
};

const normalizePath = (value: string | undefined): string | undefined => {
	const trimmed = value?.trim();
	if (!trimmed) {
		return undefined;
	}
	return trimmed;
};

export const buildInterpreterCandidates = (
	configPath: string | undefined,
	pythonExtensionPath: string | undefined,
	pathCandidates: readonly string[] = DEFAULT_PATH_CANDIDATES
): InterpreterCandidate[] => {
	const normalizedConfig = normalizePath(configPath);
	if (normalizedConfig) {
		return [{ path: normalizedConfig, source: 'config' }];
	}

	const candidates: InterpreterCandidate[] = [];
	const normalizedExtension = normalizePath(pythonExtensionPath);
	if (normalizedExtension) {
		candidates.push({ path: normalizedExtension, source: 'pythonExtension' });
	}

	for (const candidate of pathCandidates) {
		const normalizedCandidate = normalizePath(candidate);
		if (normalizedCandidate) {
			candidates.push({ path: normalizedCandidate, source: 'path' });
		}
	}

	return candidates;
};

export const mergeEnv = (
	base: NodeJS.ProcessEnv,
	overrides: Record<string, string> | undefined
): NodeJS.ProcessEnv => {
	return { ...base, ...(overrides ?? {}) };
};

export const buildServerCommand = (interpreterPath: string): { command: string; args: string[] } => {
	return {
		command: interpreterPath,
		args: ['-m', 'q2lsp', '--transport', 'stdio'],
	};
};

export const getUnsupportedPlatformMessage = (platform: NodeJS.Platform): string | undefined => {
	if (platform !== 'win32') {
		return undefined;
	}

	return "q2lsp doesn't run on native Windows. Use WSL or Remote Linux/macOS.";
};

export const buildMissingInterpreterMessage = (): string => {
	return 'Python interpreter not found for q2lsp. Set q2lsp.interpreterPath or install Python extension.';
};


export const buildInterpreterValidationSnippet = (
	modules: readonly string[] = REQUIRED_PYTHON_MODULES
): string => {
	const moduleList = JSON.stringify(modules);
	return [
		'import json',
		'import sys',
		'import importlib.util',
		`modules = ${moduleList}`,
		'missing = []',
		'for name in modules:',
		'    if importlib.util.find_spec(name) is None:',
		'        missing.append(name)',
		'print(json.dumps({"missing": missing, "executable": sys.executable, "version": sys.version}))',
	].join('\n');
};

export const parseInterpreterValidationStdout = (
	stdout: string | undefined
): InterpreterValidationDetails | null => {
	const trimmed = stdout?.trim();
	if (!trimmed) {
		return null;
	}

	try {
		const parsed = JSON.parse(trimmed) as {
			missing?: unknown;
			executable?: unknown;
			version?: unknown;
		};
		if (!Array.isArray(parsed.missing)) {
			return null;
		}
		const executable = typeof parsed.executable === 'string' ? parsed.executable : undefined;
		const version = typeof parsed.version === 'string' ? parsed.version : undefined;
		if (!executable || !version) {
			return null;
		}
		return {
			missing: parsed.missing.filter((entry): entry is string => typeof entry === 'string'),
			executable,
			version,
		};
	} catch {
		return null;
	}
};

export const buildInterpreterValidationMessage = (
	interpreterPath: string,
	missingModules: readonly string[] | undefined,
	_stderr: string | undefined
): string => {
	const missingDetail =
		missingModules && missingModules.length > 0 ? `Required modules missing: ${missingModules.join(', ')}.` : undefined;
	const q2cliHint = missingModules?.includes('q2cli')
		? Q2CLI_MISSING_QIIME_HINT
		: '';
	if (missingDetail) {
		return `${missingDetail}${q2cliHint}`;
	}
	return `q2lsp couldn't validate interpreter ${interpreterPath}. See q2lsp log for details.`;
};

export const isAbsolutePath = (value: string): boolean => {
	return path.isAbsolute(value);
};

export const buildInterpreterPathNotAbsoluteMessage = (_interpreterPath: string): string => {
	return 'q2lsp.interpreterPath must be absolute (e.g., /usr/bin/python3).';
};

export const shouldRestartOnConfigChange = (affectsConfiguration: (section: string) => boolean): boolean => {
	return affectsConfiguration('q2lsp.interpreterPath') || affectsConfiguration('q2lsp.serverEnv');
};
