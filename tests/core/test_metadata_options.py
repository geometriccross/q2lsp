"""Metadata CLI option identities shared by diagnostics and completions."""

from __future__ import annotations

import pytest

from q2lsp.core.diagnostics import collect_diagnostics
from q2lsp.core.diagnostics.codes import MISSING_REQUIRED_OPTION
from q2lsp.core.document import analyze_document
from q2lsp.qiime.catalog import QiimeCatalog
from tests.helpers.completions import complete


@pytest.mark.parametrize(
    ("arguments", "remaining"),
    [
        ("", {"--m-metadata-file", "--m-metadata-column"}),
        ("--m-metadata-file metadata.tsv", {"--m-metadata-column"}),
        ("--m-metadata-column group", {"--m-metadata-file"}),
        ("--m-metadata-file metadata.tsv --m-metadata-column group", set()),
        ("--m-metadata-column group --m-metadata-file metadata.tsv", set()),
        ("--m-metadata-file=metadata.tsv --m-metadata-column=group", set()),
    ],
)
def test_metadata_column_options_are_independent(
    arguments: str, remaining: set[str]
) -> None:
    catalog = QiimeCatalog.from_hierarchy(
        {
            "qiime": {
                "diversity": {
                    "beta-group-significance": {
                        "signature": [
                            {
                                "name": "metadata",
                                "type": "parameter",
                                "metadata": "column",
                                "description": "Categorical sample metadata",
                            },
                        ],
                    },
                },
            },
        }
    )
    source = f"qiime diversity beta-group-significance {arguments}"
    issues = collect_diagnostics(analyze_document(source), catalog)
    assert all(issue.code == MISSING_REQUIRED_OPTION for issue in issues)
    assert {issue.message for issue in issues} == {
        f"Required option '{label}' is not specified." for label in remaining
    }

    items = complete(source + " --", catalog)
    assert {item.label for item in items} == remaining | {"--help"}
    assert {item.label for item in items if "(required)" in item.detail} == remaining
