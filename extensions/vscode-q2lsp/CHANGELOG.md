# Change Log

All notable changes to the "qiime-language-server" extension will be documented in this file.

Check [Keep a Changelog](http://keepachangelog.com/) for recommendations on how to structure this file.

## [Unreleased]

- No changes yet.

## [3.0.0] - 2026-02-11

### Added
- Diagnostic validation pipeline with centralized code registry and severity mapping
- Required parameter detection (`param_is_required`) with `qiime_signature_kind` support
- CI quality gate workflow (ruff, pyright, pytest)
- Automated release pipeline with Trusted Publishing for PyPI and VS Code Marketplace
- Cross-feature consistency tests for structural integrity
- Release security hardening (CODEOWNERS, branch/tag protections)

### Changed
- Validator refactored into focused pipeline modules (structural split from monolithic validator.py)
- Global state (cache, server instance) removed from LSP layer
- Type contracts tightened from `JsonObject` to `ActionSignatureParameter`
- Used-option normalization unified via shared `normalize_option_to_param_name`
- Metadata key filter constants consolidated into `qiime/hierarchy_keys.py`
- Signature param query functions extracted into shared module
- Project license changed from proprietary to MIT

### Fixed
- Required argument detection for `qiime metadata tabulate` and similar commands
- Diagnostics validator suggestion/prefix logic
- Circular import regression across diagnostics submodules

## [2.1.0] - 2026-02-08

- Updated popup copy to be more concise.
- Added a link to the official QIIME amplicon quickstart when q2cli is missing: https://library.qiime2.org/quickstart/amplicon
- Simplified action sets and retained the log action for generic failures.
