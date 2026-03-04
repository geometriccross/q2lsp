import { type ExecFileOptionsWithStringEncoding } from 'child_process';
import * as vscode from 'vscode';
import {
	Q2CLI_MISSING_QIIME_HINT,
	QIIME2_QUICKSTART_URL,
	type InterpreterCandidate,
} from './helpers';
import { execFileForValidation, type ValidationResult } from './interpreter';

const validationTimeoutMs = 2000;

const formatOutputSnippet = (value: string | undefined): string => {
	const trimmed = value?.trim();
	if (!trimmed) {
		return '<empty>';
	}

	if (trimmed.length > 400) {
		return `${trimmed.slice(0, 400)}...`;
	}

	return trimmed;
};

const buildDiagnoseErrorMessage = (validation: ValidationResult): string => {
	if (!validation.missingModules?.length) {
		return "q2lsp couldn't validate this interpreter. See q2lsp log for details.";
	}

	const q2cliHint = validation.missingModules.includes('q2cli') ? Q2CLI_MISSING_QIIME_HINT : '';
	return `Required modules missing: ${validation.missingModules.join(', ')}.${q2cliHint}`;
};

export const selectInterpreterCandidate = async (
	candidates: InterpreterCandidate[]
): Promise<InterpreterCandidate | undefined> => {
	if (candidates.length === 1) {
		return candidates[0];
	}

	const items = candidates.map((candidate) => ({
		label: candidate.path,
		description:
			candidate.source === 'config'
				? 'Configured'
				: candidate.source === 'pythonExtension'
					? 'Python extension'
					: 'PATH',
		candidate,
	}));

	const selection = await vscode.window.showQuickPick(items, {
		placeHolder: 'Select a Python interpreter to diagnose q2lsp',
	});

	return selection?.candidate;
};

export const buildRepairActions = (missingModules: string[] | undefined): string[] => {
	const hasMissingQ2cli = missingModules?.includes('q2cli') ?? false;
	const actions = [
		'Select Python Interpreter',
		'Open Settings',
		hasMissingQ2cli ? 'Open QIIME 2 Quickstart' : 'Open README',
		'Show q2lsp Log',
	];

	if (missingModules?.includes('q2lsp')) {
		return ['Install q2lsp', ...actions];
	}

	return actions;
};

export const manageWorkspaceTrust = async (): Promise<void> => {
	const commands = ['workbench.action.manageTrust', 'workbench.trust.manage', 'workbench.action.openWorkspaceTrustEditor'];
	for (const command of commands) {
		try {
			await vscode.commands.executeCommand(command);
			return;
		} catch {
			// ignore
		}
	}
};

export const showDiagnoseMessage = async (params: {
	context: vscode.ExtensionContext;
	outputChannel?: vscode.OutputChannel;
	validation: ValidationResult;
	interpreterPath: string;
}): Promise<void> => {
	const { context, outputChannel, validation, interpreterPath } = params;
	const actions = buildRepairActions(validation.missingModules);
	const message = validation.ok
		? 'Environment is ready. q2lsp checks passed.'
		: buildDiagnoseErrorMessage(validation);
	const selection = validation.ok
		? await vscode.window.showInformationMessage(message, ...actions)
		: await vscode.window.showErrorMessage(message, ...actions);

	if (!selection) {
		return;
	}

	await handleRepairSelection({ context, outputChannel, selection, interpreterPath });
};

export const showValidationError = async (params: {
	context: vscode.ExtensionContext;
	outputChannel?: vscode.OutputChannel;
	message: string;
	validation: ValidationResult;
	interpreterPath: string;
}): Promise<void> => {
	const { context, outputChannel, message, validation, interpreterPath } = params;
	const actions = buildRepairActions(validation.missingModules);
	const selection = await vscode.window.showErrorMessage(message, ...actions);

	if (!selection) {
		return;
	}

	await handleRepairSelection({ context, outputChannel, selection, interpreterPath });
};

const handleRepairSelection = async (params: {
	context: vscode.ExtensionContext;
	outputChannel?: vscode.OutputChannel;
	selection: string;
	interpreterPath: string;
}): Promise<void> => {
	const { context, outputChannel, selection, interpreterPath } = params;
	switch (selection) {
		case 'Select Python Interpreter':
			await selectPythonInterpreter();
			return;
		case 'Open Settings':
			await vscode.commands.executeCommand('workbench.action.openSettings', 'q2lsp.interpreterPath');
			return;
		case 'Open QIIME 2 Quickstart':
			await vscode.env.openExternal(vscode.Uri.parse(QIIME2_QUICKSTART_URL));
			return;
		case 'Open README':
			await openReadme(context);
			return;
		case 'Show q2lsp Log':
			outputChannel?.show(true);
			return;
		case 'Install q2lsp':
			if (interpreterPath) {
				await confirmAndInstallQ2lsp(interpreterPath, outputChannel);
			}
			return;
		default:
			return;
	}
};

const confirmAndInstallQ2lsp = async (
	interpreterPath: string,
	outputChannel: vscode.OutputChannel | undefined
): Promise<void> => {
	const command = `"${interpreterPath}" -m pip install -U q2lsp`;
	const selection = await vscode.window.showWarningMessage(
		'Install q2lsp in this interpreter now?',
		{ modal: true },
		'Install q2lsp'
	);

	if (selection !== 'Install q2lsp') {
		return;
	}

	const hasPip = await checkPipAvailable(interpreterPath, outputChannel);
	if (!hasPip) {
		vscode.window.showErrorMessage('pip is not available for this interpreter. Install pip, then retry.');
		return;
	}

	const terminal = vscode.window.createTerminal({ name: 'q2lsp Install' });
	terminal.show(true);
	terminal.sendText(command);
};

const checkPipAvailable = async (
	interpreterPath: string,
	outputChannel: vscode.OutputChannel | undefined
): Promise<boolean> => {
	return new Promise((resolve) => {
		const execOptions: ExecFileOptionsWithStringEncoding = {
			encoding: 'utf8',
			timeout: validationTimeoutMs,
		};

		execFileForValidation(interpreterPath, ['-m', 'pip', '--version'], execOptions, (error, stdout, stderr) => {
			if (error || !stdout?.trim()) {
				outputChannel?.appendLine(
					`pip check failed for ${interpreterPath}. stderr: ${formatOutputSnippet(stderr)}`
				);
				resolve(false);
				return;
			}

			resolve(true);
		});
	});
};

const selectPythonInterpreter = async (): Promise<void> => {
	const pythonExtension = vscode.extensions.getExtension('ms-python.python');
	if (!pythonExtension) {
		vscode.window.showErrorMessage('Install the VS Code Python extension to select a Python interpreter.');
		return;
	}

	try {
		await vscode.commands.executeCommand('python.setInterpreter');
	} catch (error) {
		vscode.window.showErrorMessage(
			`Unable to open Python interpreter selection. Ensure the Python extension is installed. (${String(error)})`
		);
	}
};

const openReadme = async (context: vscode.ExtensionContext): Promise<void> => {
	const readmeUri = vscode.Uri.joinPath(context.extensionUri, 'README.md');
	const document = await vscode.workspace.openTextDocument(readmeUri);
	await vscode.window.showTextDocument(document, { preview: false });
};
