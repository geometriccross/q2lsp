"""Unified diagnostics collector."""

from __future__ import annotations

from q2lsp.lsp.diagnostics.command_analysis import analyze_command
from q2lsp.lsp.diagnostics.diagnostic_issue import DiagnosticIssue
from q2lsp.lsp.diagnostics.document_level import collect_document_diagnostics
from q2lsp.lsp.document_commands import AnalyzedDocument
from q2lsp.qiime.catalog import QiimeCatalog


def collect_diagnostics(
    document: AnalyzedDocument, catalog: QiimeCatalog
) -> list[DiagnosticIssue]:
    """Collect command-level diagnostics, then document-level diagnostics."""
    command_analyses = tuple(
        analyze_command(command, catalog, document.merged_text)
        for command in document.commands
    )

    issues = [issue for analysis in command_analyses for issue in analysis.issues]
    issues.extend(collect_document_diagnostics(command_analyses))
    return issues
