"""Standalone diagnostics computation for QIIME shell documents."""

from __future__ import annotations

from lsprotocol import types
from pygls.workspace import TextDocument

from q2lsp.lsp.adapter import offset_to_position
from q2lsp.lsp.diagnostics import analyze_command
from q2lsp.lsp.diagnostics.codes import DEFAULT_SEVERITY, DIAGNOSTIC_SEVERITY
from q2lsp.lsp.document_commands import analyze_document, to_original_offset
from q2lsp.qiime.catalog import CatalogProvider


def compute_diagnostics(
    document: TextDocument,
    get_catalog: CatalogProvider,
) -> list[types.Diagnostic]:
    """Return LSP diagnostics for QIIME commands in a text document."""
    doc = analyze_document(document.source)
    catalog = get_catalog()

    diagnostics: list[types.Diagnostic] = []
    for cmd in doc.commands:
        analysis = analyze_command(cmd, catalog, doc.merged_text)
        for issue in analysis.issues:
            original_start = to_original_offset(doc, issue.start)
            original_end = to_original_offset(doc, issue.end)

            start_pos = offset_to_position(document, original_start)
            end_pos = offset_to_position(document, original_end)

            diagnostics.append(
                types.Diagnostic(
                    range=types.Range(start=start_pos, end=end_pos),
                    message=issue.message,
                    severity=DIAGNOSTIC_SEVERITY.get(issue.code, DEFAULT_SEVERITY),
                    source="q2lsp",
                    code=issue.code,
                )
            )

    return diagnostics
