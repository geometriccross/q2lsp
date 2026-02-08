# q2lsp
[![quality-gate](https://github.com/geometriccross/q2lsp/actions/workflows/quality-gate.yml/badge.svg)](https://github.com/geometriccross/q2lsp/actions/workflows/quality-gate.yml)
[![vscode-extension-ci](https://github.com/geometriccross/q2lsp/actions/workflows/vscode-extension-ci.yml/badge.svg)](https://github.com/geometriccross/q2lsp/actions/workflows/vscode-extension-ci.yml)
[![agents-md](https://github.com/geometriccross/q2lsp/actions/workflows/agents-md.yml/badge.svg)](https://github.com/geometriccross/q2lsp/actions/workflows/agents-md.yml)

`q2lsp` is a language server protocol (LSP) implementation for QIIME 2 workflows.

![Image](https://github.com/user-attachments/assets/d628fb44-31a0-4437-b8f5-d9013480adaa)

## Getting Started
### Requirements

q2lsp can be installed via [PyPI](https://pypi.org/project/q2lsp/).  
But lsp requires the qiime2 library to be installed in envirnment.

### VSCode Extension
q2lsp is available as a [VS Code extension](./extensions/vscode-q2lsp/README.md).
You can install q2lsp via extension.

### Install Command
```bash
pip install q2lsp
```

## Development

This repository uses Pixi for local development.

```bash
pixi run -e dev pytest
pixi run -e dev ruff check .
pixi run -e dev pyright
```

## VS Code Extension

The extension implementation and usage notes are documented in
`extensions/vscode-q2lsp/README.md`.
