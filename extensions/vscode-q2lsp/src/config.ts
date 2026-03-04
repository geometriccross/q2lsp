import * as vscode from 'vscode';

export type Q2lspResolvedConfig = {
	interpreterPath?: string;
	serverEnvOverrides: Record<string, string>;
};

export const normalizeConfiguredInterpreterPath = (value: string | undefined): string | undefined => {
	const trimmed = value?.trim();
	return trimmed ? trimmed : undefined;
};

export const sanitizeServerEnvOverrides = (value: unknown): Record<string, string> => {
	if (!value || typeof value !== 'object') {
		return {};
	}

	const overrides: Record<string, string> = {};
	for (const [key, entry] of Object.entries(value as Record<string, unknown>)) {
		if (typeof entry === 'string') {
			overrides[key] = entry;
		}
	}

	return overrides;
};

export const resolveQ2lspConfig = (activeDocument: vscode.TextDocument | undefined): Q2lspResolvedConfig => {
	const configScope = activeDocument?.uri;
	const configuration = configScope
		? vscode.workspace.getConfiguration('q2lsp', configScope)
		: vscode.workspace.getConfiguration('q2lsp');

	return {
		interpreterPath: normalizeConfiguredInterpreterPath(configuration.get<string>('interpreterPath')),
		serverEnvOverrides: sanitizeServerEnvOverrides(configuration.get<unknown>('serverEnv')),
	};
};
