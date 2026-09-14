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

## Publishing (maintainers)

The extension ID is `geometriccross.qiime-language-server`: `publisher` in `package.json` is the Open VSX namespace, and `name` is the extension name. Keep both unchanged when publishing updates. The manifest already includes the version, MIT license, repository, and VS Code engine requirement; Open VSX does not need a separate manifest.

### One-time Open VSX setup

1. Sign the [Open VSX Publisher Agreement](https://github.com/eclipse/openvsx/wiki/Publishing-Extensions) with your linked Eclipse account. Generating an access token alone is not sufficient.
2. Make the token available locally as `OVSX_PAT` using a secret manager or a hidden shell prompt. Do not put it in `package.json`, a committed file, or a command-line argument.
3. Check [your namespaces](https://open-vsx.org/user-settings/namespaces). Only if `geometriccross` does not already exist, create it from the repository root:

   ```bash
   pixi run -e dev pnpm dlx ovsx@0.10.9 create-namespace geometriccross
   ```

4. Check that your token can publish to the namespace:

   ```bash
   pixi run -e dev pnpm dlx ovsx@0.10.9 verify-pat geometriccross
   ```

Creating a namespace grants contributor access, not verified ownership. To have the extension marked as verified, [claim namespace ownership](https://github.com/eclipse/openvsx/wiki/Namespace-Access#how-to-claim-a-namespace). If the namespace already exists but you cannot publish to it, resolve membership or ownership before proceeding.

### GitHub Actions releases

In this repository's **Settings → Environments → openvsx**, add an environment secret named `OVSX_ACCESS_TOKEN`. The release workflow passes this secret to the CLI as `OVSX_PAT`. With GitHub CLI, you can set it through a hidden interactive prompt:

```bash
gh secret set OVSX_ACCESS_TOKEN --env openvsx --repo geometriccross/q2lsp
```

After committing and pushing the workflow changes, run `extension-release` from the Actions UI with `dry_run` enabled. This builds, lints, tests, and uploads a VSIX artifact without publishing.

For a release, push a tag named `vscode-q2lsp-v<version>` matching `package.json` (for example, `vscode-q2lsp-v4.1.0`). **A release tag publishes the same VSIX to both VS Code Marketplace and Open VSX**; the Marketplace job also requires `AZURE_ACCESS_TOKEN` in its `vscode-marketplace` environment. Manual runs publish only when the selected ref is a matching release tag and `dry_run` is disabled. Branch runs never publish.

### Publish only to Open VSX

For the first Open VSX upload, or to avoid republishing to VS Code Marketplace, download and extract the VSIX artifact from a successful dry run. With `OVSX_PAT` set and namespace access checked, run from the repository root:

```bash
pixi run -e dev pnpm dlx ovsx@0.10.9 publish /path/to/qiime-language-server-4.1.0.vsix
unset OVSX_PAT
```

Use the actual downloaded filename and confirm its version before publishing. After the CLI reports success, check the metadata at [Open VSX](https://open-vsx.org/extension/geometriccross/qiime-language-server). Use a new version number for subsequent releases.
