"""Diagnostic code constants and severity mappings."""

from lsprotocol import types

UNKNOWN_ROOT = "q2lsp-dni/unknown-root"
UNKNOWN_ACTION = "q2lsp-dni/unknown-action"
UNKNOWN_SUBCOMMAND = "q2lsp-dni/unknown-subcommand"
UNKNOWN_OPTION = "q2lsp-dni/unknown-option"
MISSING_REQUIRED_OPTION = "q2lsp-dni/missing-required-option"

DIAGNOSTIC_SEVERITY: dict[str, types.DiagnosticSeverity] = {
    MISSING_REQUIRED_OPTION: types.DiagnosticSeverity.Error,
}

DEFAULT_SEVERITY: types.DiagnosticSeverity = types.DiagnosticSeverity.Warning
