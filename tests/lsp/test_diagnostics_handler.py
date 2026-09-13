"""Behavior tests for standalone diagnostics handler."""

from __future__ import annotations

from lsprotocol import types
from q2lsp.core.document import Document, analyze_document
from q2lsp.lsp.features import compute_diagnostics
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.types import CommandHierarchy


def _document(source: str) -> Document:
    return analyze_document(source)


def _dependency_hierarchy() -> CommandHierarchy:
    return {
        "qiime": {
            "name": "qiime",
            "demo": {
                "name": "demo",
                "step": {
                    "name": "step",
                    "signature": [
                        {"name": "table", "type": "input"},
                        {"name": "result", "type": "output"},
                    ],
                },
            },
        }
    }


def test_non_qiime_document_does_not_load_catalog() -> None:
    def fail_catalog() -> QiimeCatalog:
        raise AssertionError("Non-QIIME documents must not trigger discovery")

    assert compute_diagnostics(_document("echo hello"), fail_catalog) == []


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


def test_compute_diagnostics_reports_duplicate_output_paths() -> None:
    """Duplicate output path diagnostics are published as LSP diagnostics."""
    source = "\n".join(
        [
            "qiime demo step --i-table in-1.qza --o-result dup.qza",
            "qiime demo step --i-table in-2.qza --o-result dup.qza",
        ]
    )

    diagnostics = compute_diagnostics(
        _document(source),
        lambda: QiimeCatalog.from_hierarchy(_dependency_hierarchy()),
    )

    duplicate_diagnostics = [
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.code == "q2lsp-dni/duplicate-output-path"
    ]
    assert len(duplicate_diagnostics) == 2
    assert {diagnostic.message for diagnostic in duplicate_diagnostics} == {
        "Duplicate output path 'dup.qza' is produced by multiple commands.",
    }
    assert {
        (
            diagnostic.range.start.line,
            diagnostic.range.start.character,
            diagnostic.range.end.line,
            diagnostic.range.end.character,
        )
        for diagnostic in duplicate_diagnostics
    } == {
        (0, 46, 0, 53),
        (1, 46, 1, 53),
    }
    assert all(
        diagnostic.severity == types.DiagnosticSeverity.Error
        for diagnostic in duplicate_diagnostics
    )


def test_compute_diagnostics_reports_dependency_cycles() -> None:
    """Dependency cycle diagnostics are published as LSP diagnostics."""
    first_line = "qiime demo step --i-table b.qza --o-result a.qza"
    second_line = "qiime demo step --i-table a.qza --o-result b.qza"
    source = "\n".join([first_line, second_line])

    diagnostics = compute_diagnostics(
        _document(source),
        lambda: QiimeCatalog.from_hierarchy(_dependency_hierarchy()),
    )

    cycle_diagnostics = [
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.code == "q2lsp-dni/dependency-cycle"
    ]
    assert len(cycle_diagnostics) == 2
    assert {diagnostic.message for diagnostic in cycle_diagnostics} == {
        "Dependency cycle detected for input path 'a.qza'.",
        "Dependency cycle detected for input path 'b.qza'.",
    }
    assert {
        (
            diagnostic.range.start.line,
            diagnostic.range.start.character,
            diagnostic.range.end.line,
            diagnostic.range.end.character,
        )
        for diagnostic in cycle_diagnostics
    } == {
        (0, first_line.index("b.qza"), 0, first_line.index("b.qza") + len("b.qza")),
        (
            1,
            second_line.index("a.qza"),
            1,
            second_line.index("a.qza") + len("a.qza"),
        ),
    }
    assert all(
        diagnostic.severity == types.DiagnosticSeverity.Error
        for diagnostic in cycle_diagnostics
    )
