# AGENTS.md
## Overview
This file is the onboarding index and working agreement for this repo. Keep it concise and aligned with current behavior.

## Canonical Sources
- `src/q2lsp/` core implementation.
- `tests/` pytest suite.
- `pyproject.toml` tool and environment configuration (ruff, pyright, pytest, pixi).
- `extensions/vscode-q2lsp/README.md` VS Code extension docs; the extension lives in `extensions/vscode-q2lsp/`.

## Architecture Boundaries
- `src/q2lsp/core/` owns immutable document analysis, completion rules, and diagnostics. It MAY use catalog facts/pure qiime helpers, but MUST NOT import LSP libraries or q2cli/click.
- `src/q2lsp/lsp/` owns protocol registration, response conversion, and per-server document/diagnostic lifecycle.
- `src/q2lsp/qiime/` owns QIIME 2 discovery, help, catalog facts, and option conventions; it MUST NOT depend on core or LSP.
- See `docs/architecture.md` for data flow, coordinate contracts, and feature extension points.
- How to verify: `tests/core/test_import_boundaries.py` and import-direction review. Pyright checks types, not architectural boundaries.

## Local Dev (Pixi)
Pixi is the supported local environment manager. Use the dev environment for all checks.
See `extensions/vscode-q2lsp/README.md` for how the extension launches the server (e.g., `python -m q2lsp --transport stdio`).

```
pixi run -e dev pytest
pixi run -e dev ruff check .
pixi run -e dev ruff format .
pixi run -e dev pyright
```

## Working Agreements
- MUST keep lint clean. How to verify: `pixi run -e dev ruff check .`
- MUST keep formatting consistent. How to verify: `pixi run -e dev ruff format .`
- MUST add types for new or modified code; typecheck must pass. How to verify: `pixi run -e dev pyright`.
- MUST keep tests passing for touched areas. How to verify: `pixi run -e dev pytest`.
- MUST NOT introduce inheritance in new code; SHOULD keep implementations simple and layered. How to verify: code review (types via `pixi run -e dev pyright`).

## Testing notes
- Tests are under `tests/` and run with `pytest`.
- See `pyproject.toml` for pytest configuration.

## QIIME2/q2cli traps
### Import
Do not import or construct RootCommand via `q2cli` directly.

```python
import q2cli
q2cli.commands.RootCommand()
```

```bash
Traceback(most recent call last):
    File "/home/geometriccross/projects/q2gui/./main.py", line 14, in <module >
    root = q2cli.commands.RootCommand()
AttributeError: module 'q2cli' has no attribute 'commands'
```

Import RootCommand like this. How to verify: `pixi run -e dev python -c "from q2cli.commands import RootCommand; RootCommand()"`.

```python
from q2cli.commands import RootCommand
```

### Get Command Instance
When obtaining an instance of a command defined in qiime2, use `from q2cli.commands import RootCommand`. You can also obtain an instance from `PluginManager`, but do not use it in this case because it cannot retrieve builtin commands. How to verify: `pixi run -e dev pyright`.

### Q2 Command Execution
QIIME 2 commands are typically VERY heavy processes, except for help commands. Avoid running non-help commands unless you intend to execute a real workflow. How to verify: `pixi run -e dev pytest`.

## References
### pygls
In this repository, pygls is available for LSP implementation.  
pygls ref: https://pygls.readthedocs.io/en/latest/

### qiime2
QIIME 2 is a framework for bioinformatics written in Python. While QIIME 2 is commonly used via the CLI, an API is also provided in Python, allowing native handling of its commands.
The library used for QIIME 2 as a CLI is called `click`. QIIME 2 is built upon the foundation of `click`.  
qiime2 ref: https://amplicon-docs.qiime2.org/en/stable/

### click
click ref: https://click.palletsprojects.com/en/stable/
