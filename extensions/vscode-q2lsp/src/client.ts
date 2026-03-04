import * as vscode from 'vscode';
import {
	LanguageClient,
	type LanguageClientOptions,
	type ServerOptions,
} from 'vscode-languageclient/node';
import { buildServerCommand, mergeEnv } from './helpers';

export interface Q2lspClientLaunchOptions {
	interpreterPath: string;
	cwd?: string;
	serverEnv?: Record<string, string>;
	outputChannel?: vscode.OutputChannel;
}

export const buildQ2lspServerOptions = (options: Q2lspClientLaunchOptions): ServerOptions => {
	const serverCommand = buildServerCommand(options.interpreterPath);
	const run = {
		command: serverCommand.command,
		args: serverCommand.args,
		options: {
			cwd: options.cwd,
			env: mergeEnv(process.env, options.serverEnv),
		},
	};
	const debug = {
		command: serverCommand.command,
		args: serverCommand.args,
		options: {
			cwd: options.cwd,
			env: mergeEnv(process.env, options.serverEnv),
		},
	};

	return {
		run,
		debug,
	};
};

export const buildQ2lspClientOptions = (
	outputChannel?: vscode.OutputChannel
): LanguageClientOptions => {
	return {
		documentSelector: [{ language: 'shellscript', scheme: 'file' }],
		outputChannel,
	};
};

export const startQ2lspClient = async (options: Q2lspClientLaunchOptions): Promise<LanguageClient> => {
	const serverOptions = buildQ2lspServerOptions(options);
	const clientOptions = buildQ2lspClientOptions(options.outputChannel);
	const client = new LanguageClient('q2lsp', 'q2lsp', serverOptions, clientOptions);
	try {
		await client.start();
		return client;
	} catch (error) {
		try {
			await client.dispose();
		} catch {
			// ignore cleanup failure
		}
		throw error;
	}
};

export const stopQ2lspClient = async (client: LanguageClient | undefined): Promise<void> => {
	if (!client) {
		return;
	}

	await client.stop();
};
