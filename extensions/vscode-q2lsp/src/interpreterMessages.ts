export const QIIME2_QUICKSTART_URL = 'https://library.qiime2.org/quickstart/amplicon';
export const Q2CLI_MISSING_QIIME_HINT =
	` QIIME 2 is not installed in this Python environment (missing q2cli). Install QIIME 2: ${QIIME2_QUICKSTART_URL}.`;

export const formatOutputSnippet = (value: string | undefined): string => {
	const trimmed = value?.trim();
	if (!trimmed) {
		return '<empty>';
	}
	if (trimmed.length > 400) {
		return `${trimmed.slice(0, 400)}...`;
	}
	return trimmed;
};

export const buildMissingInterpreterMessage = (): string => {
	return 'Python interpreter not found for q2lsp. Set q2lsp.interpreterPath or install Python extension.';
};

const buildMissingModulesMessage = (missingModules: readonly string[] | undefined): string | undefined => {
	if (!missingModules?.length) {
		return undefined;
	}

	const q2cliHint = missingModules.includes('q2cli')
		? Q2CLI_MISSING_QIIME_HINT
		: '';
	return `Required modules missing: ${missingModules.join(', ')}.${q2cliHint}`;
};

export const buildInterpreterValidationMessage = (
	interpreterPath: string,
	missingModules: readonly string[] | undefined
): string => {
	const missingModulesMessage = buildMissingModulesMessage(missingModules);
	if (missingModulesMessage) {
		return missingModulesMessage;
	}
	return `q2lsp couldn't validate interpreter ${interpreterPath}. See q2lsp log for details.`;
};

export const buildDiagnoseInterpreterValidationMessage = (
	missingModules: readonly string[] | undefined
): string => {
	const missingModulesMessage = buildMissingModulesMessage(missingModules);
	if (missingModulesMessage) {
		return missingModulesMessage;
	}
	return "q2lsp couldn't validate this interpreter. See q2lsp log for details.";
};

export const buildInterpreterPathNotAbsoluteMessage = (): string => {
	return 'q2lsp.interpreterPath must be absolute (e.g., /usr/bin/python3).';
};
