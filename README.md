# q2lsp

`q2lsp` is a language server protocol (LSP) implementation for QIIME 2 workflows.

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
