# q2lsp VS Code Extension

This extension launches the q2lsp language server via `python -m q2lsp --transport stdio` when you open shell scripts.

![Image](https://raw.githubusercontent.com/geometriccross/q2lsp/refs/heads/images/props/demo_window_captured.gif)

## Supported platforms

- Linux
- macOS
- WSL (via VS Code Remote - WSL)

Native Windows is not supported. Use WSL or a remote Linux/macOS environment.

## Setup

Run **q2lsp: Open Setup Wizard** from the Command Palette, or select **Set Up QIIME 2** under **Welcome: Open Walkthrough**.

1. **Set up your QIIME 2 environment**: choose an existing Python interpreter, browse for one, or create an environment with Conda or Pixi. Manual setup links to the QIIME 2 Quickstart. New environments use the official environment list; creation requires confirmation.
2. **Prepare q2lsp**: check the selected interpreter and, if needed, confirm installation of q2lsp into that environment.
3. **Check and save your setup**: recheck the Python packages, then save the absolute interpreter path in Workspace or User settings. Open a shell script to use q2lsp.

The walkthrough marks steps complete after successful checks, not button clicks. Selecting another interpreter clears the previous result. Setup requires a trusted workspace before running Python or environment tools. It does not run a QIIME 2 analysis.

You can also configure `q2lsp.interpreterPath` directly if your environment already contains `qiime2`, `q2cli`, and `q2lsp`.

The Python extension is optional. If it is installed and `q2lsp.interpreterPath` is not set, the extension will use the active Python interpreter (falling back to `python3`/`python` on PATH).
The language server inherits the VS Code extension-host environment by default (including PATH). If you rely on an activated environment, launch VS Code from that environment or set `q2lsp.interpreterPath` explicitly.

### Using QIIME 2 in a terminal

Saving the interpreter path configures q2lsp; it does not activate your terminal. After creating and checking an environment, the wizard displays its activation command and records it in the `q2lsp` output channel.

For Pixi, the wizard imports QIIME 2 as a feature and includes it in the project's **default environment**. In the selected project folder, run:

```sh
pixi shell
qiime --help
```

You can also run `pixi run qiime --help` without opening a shell. If a Pixi shell was already open before setup, run `exit` and enter it again.

Creation replaces the default environment's configuration after confirmation. It uses only the imported QIIME 2 feature (`no-default-feature = true`), so the workspace's implicit default feature cannot introduce conflicting dependencies or platforms (such as `osx-arm64` versus QIIME 2's `osx-64`). Other environment definitions are not changed. Select a new folder if you need to keep the existing default environment.

Projects created by older wizard versions may still use a named environment. To switch, replace its entry under `[environments]` in `pixi.toml` with the following, substituting the actual imported feature name, then run `pixi install`:

```toml
[environments]
default = { features = ["<qiime-feature-name>"], no-default-feature = true }
```

This creates a new environment prefix at `.pixi/envs/default`. Select its `bin/python` in the wizard and prepare q2lsp there before saving the new interpreter path.

For Conda, use `conda activate <environment-name>` before running `qiime`.

## Settings

- `q2lsp.interpreterPath` (string, optional): Absolute path to the Python interpreter used to launch q2lsp.
- `q2lsp.serverEnv` (object): Environment variable overrides applied to the language server process. These values override the inherited extension-host environment; they do not replace it. Changing this setting restarts the q2lsp server.

Example:

```jsonc
{
  "q2lsp.interpreterPath": "/opt/qiime2/bin/python",
  "q2lsp.serverEnv": {
    "PATH": "/opt/qiime2/bin:${env:PATH}"
  }
}
```

## Troubleshooting

Run the `q2lsp: Setup / Diagnose Environment` command from the Command Palette to validate your Python environment. The command reports details in the `q2lsp` output channel and suggests next steps if modules are missing.

If you see errors about importing `q2lsp`, verify the interpreter directly:

```bash
/path/to/python -c "import q2lsp"
```

If that fails, install `q2lsp` into that environment and confirm the same command succeeds.

## WSL notes

- Run VS Code in WSL (Remote - WSL).
- Set `q2lsp.interpreterPath` to the Linux path inside WSL (for example `/usr/bin/python3`).
- Do not use Windows paths; the extension host runs in the WSL environment.
