# AGENTS.md

## Overview
This file is the onboarding index and working agreement for this repo. Keep it concise and aligned with current behavior.

## Canonical Sources
- `src/q2lsp/` core implementation.
- `tests/` pytest suite.
- `pyproject.toml` tool and environment configuration (ruff, pyright, pytest, pixi).
- `extensions/vscode-q2lsp/README.md` VS Code extension docs; the extension lives in `extensions/vscode-q2lsp/`.
- `.beads/README.md` beads workflow reference.

## Architecture Boundaries
- `src/q2lsp/lsp/` handles LSP server protocol, request routing, and editor-facing behavior.
- `src/q2lsp/qiime/` handles QIIME 2 command discovery, execution helpers, and domain-specific data.
- LSP layer MAY depend on qiime helpers; qiime helpers MUST NOT depend on LSP.
- How to verify: `pixi run -e dev pyright`.

## Local Dev (Pixi)
Pixi is the supported local environment manager. Use the dev environment for all checks.
See `extensions/vscode-q2lsp/README.md` for how the extension launches the server (e.g., `python -m q2lsp --transport stdio`).

```
pixi run -e dev pytest
pixi run -e dev ruff check .
pixi run -e dev ruff format .
pixi run -e dev pyright
pixi run -e dev git-hooks-install
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

https://pygls.readthedocs.io/en/latest/

### qiime2
QIIME 2 is a framework for bioinformatics written in Python. While QIIME 2 is commonly used via the CLI, an API is also provided in Python, allowing native handling of its commands.

qiime2 ref: https://amplicon-docs.qiime2.org/en/stable/

The library used for QIIME 2 as a CLI is called `click`. QIIME 2 is built upon the foundation of `click`.


### click
click ref: https://click.palletsprojects.com/en/stable/

## Project Structure (generated)
Snapshot for navigation only; do not edit between the markers. Regenerate using `pixi run -e dev agents-structure` (or `pixi run -e dev agents-structure-check`). Fallback: `python scripts/gen_project_structure.py` (or `python scripts/gen_project_structure.py --check`).
<!-- BEGIN GENERATED: PROJECT_STRUCTURE -->
```
<Project Root>
├── .beads/
├── extensions/
│   └── vscode-q2lsp/
│       ├── .gitignore
│       ├── .npmrc
│       ├── .vscode-test.mjs
│       ├── .vscodeignore
│       ├── CHANGELOG.md
│       ├── eslint.config.mjs
│       ├── LICENSE
│       ├── package.json
│       ├── pnpm-lock.yaml
│       ├── README.md
│       ├── src/
│       │   ├── extension.ts
│       │   ├── helpers.ts
│       │   └── test/
│       │       └── extension.test.ts
│       ├── tsconfig.json
│       └── vsc-extension-quickstart.md
├── src/
│   └── q2lsp/
│       ├── __main__.py
│       ├── cli.py
│       ├── logging.py
│       ├── lsp/
│       └── qiime/
├── tests/
│   ├── __init__.py
│   ├── helpers/
│   ├── lsp/
│   ├── qiime/
│   ├── test_cli.py
│   ├── test_logging.py
│   ├── test_release_workflow_consistency.py
│   └── test_workflow_hardening.py
└── pyproject.toml
```
<!-- END GENERATED: PROJECT_STRUCTURE -->
