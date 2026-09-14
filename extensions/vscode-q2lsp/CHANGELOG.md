# Change Log

All notable changes to the "qiime-language-server" extension will be documented in this file.

Check [Keep a Changelog](http://keepachangelog.com/) for recommendations on how to structure this file.

## [Unreleased]

- No changes yet.

## [4.0.0] - 2026-09-14

### Added
- Native VS Code setup walkthrough for guided QIIME 2 environment configuration, validation, installation, and saving the selected interpreter
- Open VSX distribution alongside VS Code Marketplace
- QIIME CodeLens commands (runnable actions directly in the editor)
- Dependency cycle diagnostics across QIIME commands
- Duplicate output path detection
- Document snapshot model with UTF-16 offset mapping
- Catalog-backed q2cli metadata layer
- GitHub tree manifest fetching for QIIME plugin discovery

### Changed
- Restructured parser to group option/value tokens into units
- Integrated completion flow into usecase layer (layered completion architecture)
- Split diagnostics into command/document analysis modules
- Derive used params from grouped options in completion
- Overhauled interpreter resolution and setup flow while keeping `q2lsp.interpreterPath` as an explicit override

### Fixed
- Disambiguated `-h` as help flag vs option value
- Clarified command boundary and continuation mapping
- Fixed completion option grouping
- Fixed q2lsp Python interpreter resolution

## [3.1.0] - 2026-03-04

### Changed
- Modularized extension runtime/config/interpreter/diagnosis modules
- Improved diagnostics suggestion data flow to structured mapping
- Internal cleanup and test coverage improvements

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
