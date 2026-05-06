export interface QiimeRunCommandPayload {
	uri: string;
	commandText: string;
	tokens: string[];
}

export interface QiimeTerminal {
	sendText(text: string): void;
	show(): void;
}

export const toQiimeRunCommandPayload = (value: unknown): QiimeRunCommandPayload | undefined => {
	if (!value || typeof value !== 'object') {
		return undefined;
	}

	const candidate = value as { uri?: unknown; commandText?: unknown; tokens?: unknown };
	if (
		typeof candidate.uri !== 'string' ||
		typeof candidate.commandText !== 'string' ||
		!Array.isArray(candidate.tokens)
	) {
		return undefined;
	}

	const tokens = candidate.tokens;
	if (!tokens.every((token) => typeof token === 'string')) {
		return undefined;
	}

	return {
		uri: candidate.uri,
		commandText: candidate.commandText,
		tokens,
	};
};

export const formatQiimeRunCommandTokens = (payload: QiimeRunCommandPayload): string =>
	JSON.stringify(payload.tokens);

export const executeQiimeRunCommand = (
	payload: QiimeRunCommandPayload,
	terminal: QiimeTerminal
): void => {
	terminal.sendText(payload.commandText);
	terminal.show();
};

export const resolveQiimeRunTerminal = <TTerminal extends QiimeTerminal>(
	activeTerminal: TTerminal | undefined,
	terminals: readonly TTerminal[],
	createTerminal: () => TTerminal
): TTerminal => activeTerminal ?? terminals[0] ?? createTerminal();
