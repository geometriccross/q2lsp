import * as vscode from 'vscode';
import {
	DEFAULT_PATH_CANDIDATES,
	buildInterpreterCandidates,
	type InterpreterCandidate,
} from './interpreterSources';
import { isAbsolutePath } from './interpreterPath';
import {
	buildInterpreterPathNotAbsoluteMessage,
	buildInterpreterValidationMessage,
	buildMissingInterpreterMessage,
	formatOutputSnippet,
} from './interpreterMessages';
import { VALIDATION_TIMEOUT_MS } from './interpreter';
import * as interpreter from './interpreter';
import { showValidationError } from './diagnosis';

type PythonExtensionApi = {
	environments: {
		getActiveEnvironmentPath: () => unknown;
		resolveEnvironment: (environmentPath: unknown) => Promise<unknown>;
	};
};

const isRecord = (value: unknown): value is Record<string, unknown> => {
	return typeof value === 'object' && value !== null;
};

const pathFromUnknown = (value: unknown): string | undefined => {
	return typeof value === 'string' && value.trim() ? value.trim() : undefined;
};

const isPythonExtensionApi = (value: unknown): value is PythonExtensionApi => {
	if (!isRecord(value) || !isRecord(value.environments)) {
		return false;
	}

	return (
		typeof value.environments.getActiveEnvironmentPath === 'function' &&
		typeof value.environments.resolveEnvironment === 'function'
	);
};

const extractPythonExecutablePath = (
	resolvedEnvironment: unknown,
	activeEnvironmentPath: unknown
): string | undefined => {
	if (isRecord(resolvedEnvironment) && isRecord(resolvedEnvironment.executable)) {
		const executableUri = resolvedEnvironment.executable.uri;
		if (isRecord(executableUri)) {
			const fsPath = pathFromUnknown(executableUri.fsPath);
			if (fsPath) {
				return fsPath;
			}
		}
	}

	if (isRecord(activeEnvironmentPath)) {
		return pathFromUnknown(activeEnvironmentPath.path);
	}

	return undefined;
};

export const resolveInterpreter = async (params: {
	context: vscode.ExtensionContext;
	outputChannel?: vscode.OutputChannel;
	config: { interpreterPath?: string; serverEnv?: Record<string, string> };
}): Promise<InterpreterCandidate | undefined> => {
	const { context, outputChannel, config } = params;
	if (config.interpreterPath && !isAbsolutePath(config.interpreterPath)) {
		const message = buildInterpreterPathNotAbsoluteMessage();
		outputChannel?.appendLine(message);
		vscode.window.showErrorMessage(message);
		return undefined;
	}

	const pythonExtensionInterpreter = await resolveConfiguredPythonInterpreter(outputChannel);
	const candidates = buildInterpreterCandidates(
		config.interpreterPath,
		pythonExtensionInterpreter,
		DEFAULT_PATH_CANDIDATES
	);

	if (candidates.length === 0) {
		const message = buildMissingInterpreterMessage();
		outputChannel?.appendLine(message);
		vscode.window.showErrorMessage(message);
		return undefined;
	}

	let lastFailure: { candidate: InterpreterCandidate; validation: interpreter.ValidationResult } | undefined;
	for (const candidate of candidates) {
		const validation = await interpreter.validateInterpreter(
			interpreter.execFileForValidation,
			candidate.path,
			VALIDATION_TIMEOUT_MS
		);
		if (validation.ok) {
			return candidate;
		}
		lastFailure = { candidate, validation };

		const message = buildInterpreterValidationMessage(candidate.path, validation.missingModules);
		outputChannel?.appendLine(message);
		const detail = validation.stderr ?? validation.errorMessage;
		if (detail?.trim()) {
			outputChannel?.appendLine(`Validation detail for ${candidate.path}: ${formatOutputSnippet(detail)}`);
		}
		if (candidate.source === 'config') {
			await showValidationError({
				context,
				outputChannel,
				message,
				validation,
				interpreterPath: candidate.path,
			});
			return undefined;
		}
	}

	if (lastFailure) {
		const message = buildInterpreterValidationMessage(
			lastFailure.candidate.path,
			lastFailure.validation.missingModules
		);
		await showValidationError({
			context,
			outputChannel,
			message,
			validation: lastFailure.validation,
			interpreterPath: lastFailure.candidate.path,
		});
	}

	return undefined;
};

export const resolveConfiguredPythonInterpreter = async (
	outputChannel?: vscode.OutputChannel
): Promise<string | undefined> => {
	const pythonExtension = vscode.extensions.getExtension('ms-python.python');
	if (!pythonExtension) {
		return undefined;
	}

	try {
		await pythonExtension.activate();
	} catch (error) {
		outputChannel?.appendLine(`Failed to activate Python extension: ${String(error)}`);
	}

	try {
		const pythonApi = pythonExtension.exports;
		if (isPythonExtensionApi(pythonApi)) {
			const activeEnvironmentPath = pythonApi.environments.getActiveEnvironmentPath();
			const resolvedEnvironment = await pythonApi.environments.resolveEnvironment(activeEnvironmentPath);
			const resolvedInterpreter = extractPythonExecutablePath(resolvedEnvironment, activeEnvironmentPath);
			if (resolvedInterpreter) {
				return resolvedInterpreter;
			}
		}
	} catch (error) {
		outputChannel?.appendLine(`Failed to query Python extension environment API: ${String(error)}`);
	}

	try {
		const commandInterpreter = await vscode.commands.executeCommand<string>('python.interpreterPath');
		if (commandInterpreter && commandInterpreter.trim()) {
			return commandInterpreter.trim();
		}
	} catch (error) {
		outputChannel?.appendLine(`Failed to query legacy Python interpreter path command: ${String(error)}`);
	}

	const pythonConfig = vscode.workspace.getConfiguration('python');
	const configured = pythonConfig.get<string>('defaultInterpreterPath');
	if (configured && configured.trim()) {
		return configured.trim();
	}

	return undefined;
};
