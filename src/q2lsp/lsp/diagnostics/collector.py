"""Unified diagnostics collector."""

from __future__ import annotations

from q2lsp.lsp.diagnostics.command_level import analyze_command
from q2lsp.lsp.diagnostics.diagnostic_issue import DiagnosticIssue
from q2lsp.lsp.diagnostics.document_level import collect_document_diagnostics
from q2lsp.lsp.document_commands import AnalyzedDocument
from q2lsp.qiime.types import CommandHierarchy


def collect_diagnostics(
    document: AnalyzedDocument, hierarchy: CommandHierarchy
) -> list[DiagnosticIssue]:
    """Collect command-level diagnostics, then document-level diagnostics."""
    command_analyses = tuple(
        analyze_command(command, hierarchy, document.merged_text)
        for command in document.commands
    )

    issues = [issue for analysis in command_analyses for issue in analysis.issues]
    issues.extend(collect_document_diagnostics(command_analyses))
    return issues
