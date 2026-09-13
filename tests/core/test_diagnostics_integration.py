"""Parsing and validation through the document diagnostics entry point."""

from __future__ import annotations

import pytest

from q2lsp.core.diagnostics import collect_diagnostics
from q2lsp.core.diagnostics.codes import UNKNOWN_OPTION, UNKNOWN_ROOT
from q2lsp.core.document import analyze_document
from q2lsp.qiime.catalog import QiimeCatalog


@pytest.mark.parametrize(
    ("source", "code", "span", "suggestion"),
    [
        ("qiime feature-tabel summarize", UNKNOWN_ROOT, (6, 19), "feature-table"),
        (
            "qiime feature-table summarize --i-tabel",
            UNKNOWN_OPTION,
            (30, 39),
            "--i-table",
        ),
        ("qiime feature-table summarize --i-table table.qza", None, None, None),
    ],
)
def test_command_diagnostics(
    source: str,
    code: str | None,
    span: tuple[int, int] | None,
    suggestion: str | None,
) -> None:
    catalog = QiimeCatalog.from_hierarchy(
        {
            "qiime": {
                "feature-table": {
                    "summarize": {
                        "signature": [
                            {"name": "table", "type": "input"},
                            {
                                "name": "obs_metadata",
                                "type": "parameter",
                                "default": None,
                            },
                        ]
                    }
                }
            }
        }
    )
    issues = collect_diagnostics(analyze_document(source), catalog)
    if code is None:
        assert issues == []
    else:
        assert len(issues) == 1
        issue = issues[0]
        assert issue.code == code
        assert (issue.start, issue.end) == span
        assert f"'{suggestion}'" in issue.message
        assert "Did you mean" in issue.message
