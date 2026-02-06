# Release Policy

This document defines the release policy for automated package publishing.

Operational runbooks for executing releases and handling incidents are in
`doc/prompts/RELEASING.md`.

## 1) Publish targets

- Publish to both `TestPyPI` and `PyPI`.
- `TestPyPI` is the staging target.
- `PyPI` is the production target.

## 2) Trigger and tag policy

- Releases are tag-driven.
- Stable release tags MUST match `vX.Y.Z` (for example: `v0.4.2`).
- Prerelease tags MUST use PEP 440 prerelease versions encoded in the tag (for example: `v0.5.0rc1`, `v0.5.0b1`, `v0.5.0a1`).
- Tag behavior:
  - `vX.Y.Z`: publish to TestPyPI, then promote to PyPI after approval.
  - `vX.Y.ZaN` / `vX.Y.ZbN` / `vX.Y.ZrcN`: publish to TestPyPI only by default; do not auto-publish prereleases to PyPI.

## 3) Version source of truth

- The package version declared in `pyproject.toml` is the single source of truth.
- The release tag version MUST exactly match the package version (without the leading `v`).
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
