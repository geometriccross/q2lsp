# Release Policy

This document defines the release policy for automated Python package publishing.

Operational runbooks for executing releases and handling incidents are in
`doc/prompts/RELEASING.md`.

VS Code extension publish operations are documented in `doc/prompts/RELEASING.md`
under the `vscode-extension-release` workflow runbook.

## 1) Publish targets

- Publish to both `TestPyPI` and `PyPI`.
- `TestPyPI` is the staging target.
- `PyPI` is the production target.

## 2) Trigger and tag policy

- Releases are tag-driven.
- Python stable release tags MUST match `q2lsp-vX.Y.Z` (for example: `q2lsp-v0.4.2`).
- Python prerelease tags MUST match `q2lsp-vX.Y.ZaN` or `q2lsp-vX.Y.ZbN` (for example: `q2lsp-v0.5.0a1`, `q2lsp-v0.5.0b1`).
- Tag behavior:
  - `q2lsp-vX.Y.Z`: publish to TestPyPI, then promote to PyPI after approval.
  - `q2lsp-vX.Y.ZaN` / `q2lsp-vX.Y.ZbN`: publish to TestPyPI only by default; do not auto-publish prereleases to PyPI.

## 3) Version source of truth

- The package version declared in `pyproject.toml` is the single source of truth.
- The release tag version MUST exactly match the package version (without the leading `q2lsp-v`).
- If the tag and package version differ, release MUST fail.

## 4) Promotion and approval policy

- Promotion is a two-step flow:
  1. Build once and publish artifact(s) to TestPyPI.
  2. Promote the same artifact(s) to PyPI.
- PyPI publication requires explicit human approval (protected environment/manual gate).
- No direct publish to PyPI without a successful TestPyPI publish from the same build output.

## 5) Rollback policy

- Do not delete released artifacts as rollback.
- Rollback procedure:
  1. Yank the bad PyPI release.
  2. Publish a patch release with the fix (`X.Y.(Z+1)`).
- If needed, unyank only after explicit confirmation that the release is safe.

## 6) Minimum required checks before release

All checks below MUST pass before any TestPyPI publish:

- `pixi run -e dev ruff check .`
- `pixi run -e dev ruff format --check .`
- `pixi run -e dev pyright`
- `pixi run -e dev pytest`
- Build distributions and validate metadata (`python -m build` and `twine check dist/*`).
