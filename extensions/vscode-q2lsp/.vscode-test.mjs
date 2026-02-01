import { mkdirSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { defineConfig } from '@vscode/test-cli';

const tmpRoot = process.platform === 'win32' ? os.tmpdir() : '/tmp';
const baseDir = path.join(tmpRoot, 'vscode-q2lsp');
const runId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
const runDir = path.join(baseDir, runId);
const userDataDir = path.join(runDir, 'user-data');
const extensionsDir = path.join(runDir, 'extensions');

mkdirSync(userDataDir, { recursive: true });
mkdirSync(extensionsDir, { recursive: true });

export default defineConfig({
	files: 'out/test/**/*.test.js',
	launchArgs: [
		`--user-data-dir=${userDataDir}`,
		`--extensions-dir=${extensionsDir}`,
	],
});
