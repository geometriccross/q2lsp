# q2lsp VS Code Extension

This extension launches the q2lsp language server via `python -m q2lsp --transport stdio` when you open shell scripts.

## Supported platforms

- Linux
- macOS
- WSL (via VS Code Remote - WSL)

Native Windows is not supported. Use WSL or a remote Linux/macOS environment.

## Setup

1) Create or choose a Python environment that has `q2lsp` installed.
2) Set `q2lsp.interpreterPath` to the absolute path of that interpreter.
3) Open a shell script to activate the extension.

The Python extension is optional. If it is installed, its interpreter can be used as a fallback when `q2lsp.interpreterPath` is not set.
The language server inherits the VS Code extension-host environment by default (including PATH). If you rely on an activated environment, launch VS Code from that environment or set `q2lsp.interpreterPath` explicitly.

## Settings

- `q2lsp.interpreterPath` (string, required): Absolute path to the Python interpreter used to launch q2lsp.
- `q2lsp.serverEnv` (object): Environment variable overrides applied to the language server process. These values override the inherited extension-host environment; they do not replace it.

Example:

```jsonc
{
  "q2lsp.interpreterPath": "/opt/qiime2/bin/python",
  "q2lsp.serverEnv": {
    "QIIME2_USER_ENV": "1"
  }
}
```

## Troubleshooting

If you see errors about importing `q2lsp`, verify the interpreter directly:

```bash
/path/to/python -c "import q2lsp"
```

If that fails, install `q2lsp` into that environment and confirm the same command succeeds.

## WSL notes

- Run VS Code in WSL (Remote - WSL).
- Set `q2lsp.interpreterPath` to the Linux path inside WSL (for example `/usr/bin/python3`).
- Do not use Windows paths; the extension host runs in the WSL environment.
