import * as path from 'path';

export type InterpreterCandidateSource = 'config' | 'pythonExtension' | 'path';

export type InterpreterCandidate = {
	path: string;
	source: InterpreterCandidateSource;
};

export const DEFAULT_PATH_CANDIDATES = ['python3', 'python'] as const;

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

	return 'q2lsp does not support native Windows. Use WSL or a remote Linux/macOS environment, then set q2lsp.interpreterPath.';
};

export const buildMissingInterpreterMessage = (): string => {
	return 'Unable to resolve a Python interpreter for q2lsp. Set q2lsp.interpreterPath, install the VS Code Python extension, or ensure python3/python is on PATH.';
};

export const buildInterpreterValidationMessage = (interpreterPath: string, stderr: string | undefined): string => {
	const detail = stderr?.trim();
	if (!detail) {
		return `Failed to import q2lsp using ${interpreterPath}. Ensure q2lsp is installed in that environment.`;
	}
	return `Failed to import q2lsp using ${interpreterPath}. stderr: ${detail}`;
};

export const isAbsolutePath = (value: string): boolean => {
	return path.isAbsolute(value);
};

export const buildInterpreterPathNotAbsoluteMessage = (interpreterPath: string): string => {
	return `q2lsp.interpreterPath must be an absolute path. Received "${interpreterPath}". Set it to an absolute path like /usr/bin/python3.`;
};

export const shouldRestartOnConfigChange = (affectsConfiguration: (section: string) => boolean): boolean => {
	return affectsConfiguration('q2lsp.interpreterPath') || affectsConfiguration('q2lsp.serverEnv');
};
