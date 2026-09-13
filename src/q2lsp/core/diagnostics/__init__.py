"""Command checks followed by checks over the document's dependency graph."""

from __future__ import annotations

from q2lsp.core.diagnostics.command_analysis import analyze_command
from q2lsp.core.diagnostics.diagnostic_issue import DiagnosticIssue
from q2lsp.core.diagnostics.document_level import collect_document_diagnostics
from q2lsp.core.document import Document
from q2lsp.qiime.catalog import QiimeCatalog


def collect_diagnostics(
    document: Document, catalog: QiimeCatalog
) -> list[DiagnosticIssue]:
    analyses = tuple(
        analyze_command(command, catalog, document.merged_text)
        for command in document.commands
    )
    issues = [issue for analysis in analyses for issue in analysis.issues]
    issues.extend(collect_document_diagnostics(analyses))
    return issues
