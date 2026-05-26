import { execFile, type ExecFileException, type ExecFileOptionsWithStringEncoding } from 'child_process';
export const REQUIRED_PYTHON_MODULES = ['q2lsp', 'q2cli'] as const;
export const VALIDATION_TIMEOUT_MS = 2000;

export type InterpreterValidationDetails = {
	missing: string[];
	executable: string;
	version: string;
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

export type ValidationResult = {
	ok: boolean;
	stdout?: string;
	stderr?: string;
	errorMessage?: string;
	missingModules?: string[];
	details?: InterpreterValidationDetails;
};

export type ExecFileRunner = (
	file: string,
	args: readonly string[],
	options: ExecFileOptionsWithStringEncoding,
	callback: (error: ExecFileException | null, stdout: string, stderr: string) => void
) => void;

export const execFileForValidation: ExecFileRunner = (file, args, options, callback) => {
	execFile(file, args, options, callback);
};

export const validateInterpreter = (
	execFileFn: ExecFileRunner,
	interpreterPath: string,
	timeoutMs: number
): Promise<ValidationResult> => {
	return new Promise((resolve) => {
		const execOptions: ExecFileOptionsWithStringEncoding = {
			encoding: 'utf8',
			timeout: timeoutMs,
		};
		execFileFn(
			interpreterPath,
			['-c', buildInterpreterValidationSnippet()],
			execOptions,
			(error, stdout, stderr) => {
				if (error) {
					resolve({ ok: false, stdout, stderr, errorMessage: error.message });
					return;
				}
				const details = parseInterpreterValidationStdout(stdout);
				if (details === null) {
					const trimmed = stdout?.trim() ?? '';
					const snippet = trimmed.length > 200 ? `${trimmed.slice(0, 200)}...` : trimmed;
					resolve({
						ok: false,
						stdout,
						stderr,
						errorMessage: `Unexpected validation output (expected JSON). stdout: ${snippet}`,
					});
					return;
				}
				if (details.missing.length > 0) {
					resolve({ ok: false, stdout, stderr, missingModules: details.missing, details });
					return;
				}
				resolve({ ok: true, stdout, stderr, details });
			}
		);
	});
};
