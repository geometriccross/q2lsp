"""Diagnostics module for QIIME2 document diagnostics."""

from __future__ import annotations

from q2lsp.lsp.diagnostics.diagnostic_issue import DiagnosticIssue
from q2lsp.lsp.diagnostics.debounce import DebounceManager
from q2lsp.lsp.document_commands import AnalyzedDocument
from q2lsp.lsp.types import ParsedCommand
from q2lsp.qiime.types import CommandHierarchy


def collect_diagnostics(
    document: AnalyzedDocument, hierarchy: CommandHierarchy
) -> list[DiagnosticIssue]:
    from q2lsp.lsp.diagnostics.collector import collect_diagnostics as _collect

    return _collect(document, hierarchy)


def validate_command(
    command: ParsedCommand, hierarchy: CommandHierarchy
) -> list[DiagnosticIssue]:
    from q2lsp.lsp.diagnostics.validator import validate_command as _validate

    return _validate(command, hierarchy)


__all__ = [
    "DebounceManager",
    "DiagnosticIssue",
    "collect_diagnostics",
    "validate_command",
]
