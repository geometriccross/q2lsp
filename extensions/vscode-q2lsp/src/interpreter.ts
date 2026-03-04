import { execFile, type ExecFileException, type ExecFileOptionsWithStringEncoding } from 'child_process';
import {
	buildInterpreterValidationSnippet,
	parseInterpreterValidationStdout,
	type InterpreterValidationDetails,
} from './helpers';

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
