"""Behavior tests for standalone diagnostics handler."""

from __future__ import annotations

from lsprotocol import types
from pygls.workspace import TextDocument

from q2lsp.lsp.diagnostics_handler import compute_diagnostics
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.types import CommandHierarchy


def _document(source: str) -> TextDocument:
    return TextDocument(
        uri="file:///test.sh",
        source=source,
        language_id="shellscript",
        version=1,
    )


def test_compute_diagnostics_returns_diagnostic_for_unknown_plugin() -> None:
    """Diagnostics report unknown plugin names from the catalog."""
    hierarchy: CommandHierarchy = {
        "qiime": {
            "name": "qiime",
            "feature-table": {
                "name": "feature-table",
                "summarize": {"name": "summarize", "signature": []},
            },
        }
    }

    diagnostics = compute_diagnostics(
        _document("qiime feature-tabel summarize"),
        lambda: QiimeCatalog.from_hierarchy(hierarchy),
    )

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.range == types.Range(
        start=types.Position(line=0, character=6),
        end=types.Position(line=0, character=19),
    )
    assert diagnostic.source == "q2lsp"
    assert diagnostic.code == "q2lsp-dni/unknown-root"
    assert diagnostic.severity == types.DiagnosticSeverity.Warning
    assert "feature-tabel" in diagnostic.message


def test_compute_diagnostics_returns_empty_list_for_valid_command() -> None:
    """Diagnostics are empty for a catalog-valid command."""
    hierarchy: CommandHierarchy = {
        "qiime": {
            "name": "qiime",
            "feature-table": {
                "name": "feature-table",
                "summarize": {"name": "summarize", "signature": []},
            },
        }
    }

    diagnostics = compute_diagnostics(
        _document("qiime feature-table summarize"),
        lambda: QiimeCatalog.from_hierarchy(hierarchy),
    )

    assert diagnostics == []
