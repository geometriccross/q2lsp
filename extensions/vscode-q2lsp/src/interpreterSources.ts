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
