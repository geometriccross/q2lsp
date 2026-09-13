"""Completion behavior through real command contexts and catalog facts."""

from __future__ import annotations

import pytest
from lsprotocol import types
from q2lsp.core.document import analyze_document
from q2lsp.lsp.adapter import offset_to_position, position_to_offset

from q2lsp.core.types import CompletionKind
from q2lsp.lsp.features import handle_completion
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.catalog_facts import QiimeOptionFact
from tests.helpers.completions import complete
from tests.helpers.cursor import extract_cursor_offset


@pytest.fixture
def catalog() -> QiimeCatalog:
    return QiimeCatalog.from_hierarchy(
        {
            "qiime": {
                "builtins": ["info", "tools"],
                "info": {"short_help": "Display deployment information"},
                "tools": {"import": {"description": "Import data", "signature": []}},
                "feature-table": {
                    "short_description": "Feature table operations",
                    "summarize": {
                        "description": "Summarize a feature table",
                        "signature": [
                            {
                                "name": "table",
                                "type": "FeatureTable",
                                "description": "Input table",
                                "signature_type": "input",
                            },
                            {
                                "name": "output_dir",
                                "type": "Path",
                                "description": "Output directory",
                                "signature_type": "output",
                                "default": None,
                            },
                            {
                                "name": "sample_metadata",
                                "type": "Metadata",
                                "description": "Sample metadata",
                                "signature_type": "parameter",
                                "default": None,
                            },
                            {
                                "name": "metadata_file",
                                "type": "Metadata",
                                "description": "Metadata file",
                                "signature_type": "metadata",
                            },
                        ],
                    },
                    "filter-samples": {"signature": []},
                },
                "diversity": {"alpha": {"signature": []}},
            }
        }
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("echo hello", set()),
        ("qiime ", {"info", "tools", "feature-table", "diversity"}),
        ("qiime f", {"feature-table"}),
        ("qiime feature-table ", {"summarize", "filter-samples"}),
        ("qiime feature-table s", {"summarize"}),
        ("qiime nonexistent ", set()),
        ("qiime info ", {"--help"}),
        ("qiime info --h", {"--help"}),
        ("qiime tools ", {"import"}),
        ("qiime tools i", {"import"}),
        ("qiime tools xyz", set()),
        ("qiime tools import --", {"--help"}),
        ("qiime feature-table unknown --", set()),
        ("qiime diversity alpha --", set()),
        (
            "qiime feature-table summarize --",
            {
                "--i-table",
                "--o-output-dir",
                "--p-sample-metadata",
                "--m-metadata-file",
                "--help",
            },
        ),
        ("qiime feature-table summarize --t", {"--i-table"}),
        ("qiime feature-table summarize ta", {"--i-table"}),
        ("qiime feature-table summarize table", {"--i-table"}),
        ("qiime feature-table summarize output", {"--o-output-dir"}),
        ("qiime feature-table summarize --p-s", {"--p-sample-metadata"}),
        ("qiime feature-table summarize nonexistent", set()),
    ],
)
def test_completion_candidates(
    catalog: QiimeCatalog, source: str, expected: set[str]
) -> None:
    assert {item.label for item in complete(source, catalog)} == expected


@pytest.mark.parametrize(
    ("source", "kind", "detail"),
    [
        ("qiime info", CompletionKind.BUILTIN, "Display deployment information"),
        ("qiime feat", CompletionKind.PLUGIN, "Feature table operations"),
        ("qiime feature-table sum", CompletionKind.ACTION, "Summarize a feature table"),
        ("qiime tools imp", CompletionKind.ACTION, "Import data"),
        (
            "qiime feature-table summarize --i-t",
            CompletionKind.PARAMETER,
            "(required) [FeatureTable] Input table",
        ),
        (
            "qiime feature-table summarize --o-out",
            CompletionKind.PARAMETER,
            "[Path] Output directory",
        ),
        (
            "qiime feature-table summarize --p-s",
            CompletionKind.PARAMETER,
            "[Metadata] Sample metadata",
        ),
        (
            "qiime feature-table summarize --m-m",
            CompletionKind.PARAMETER,
            "(required) [Metadata] Metadata file",
        ),
    ],
)
def test_completion_metadata(
    catalog: QiimeCatalog, source: str, kind: CompletionKind, detail: str
) -> None:
    items = complete(source, catalog)
    assert len(items) == 1
    assert items[0].kind == kind
    assert items[0].detail == detail


@pytest.mark.parametrize("required", [False, True])
def test_explicit_requiredness_overrides_defaults(required: bool) -> None:
    catalog = QiimeCatalog.from_hierarchy(
        {
            "qiime": {
                "tools": {
                    "inspect": {
                        "signature": [
                            {"name": "level", "type": "String", "required": required}
                        ]
                    }
                }
            }
        }
    )
    item = next(
        item
        for item in complete("qiime tools inspect --", catalog)
        if item.label == "--level"
    )
    assert ("(required)" in item.detail) is required


@pytest.mark.parametrize("table_option", ["--i-table table.qza", "--i-table=table.qza"])
def test_used_options_are_excluded(catalog: QiimeCatalog, table_option: str) -> None:
    items = complete(
        f"qiime feature-table summarize {table_option} --o-output-dir out --help --",
        catalog,
    )
    assert {item.label for item in items} == {
        "--p-sample-metadata",
        "--m-metadata-file",
    }


@pytest.mark.parametrize(
    ("source", "label", "kind", "start", "end"),
    [
        ("qiime feat<CURSOR>", "feature-table", types.CompletionItemKind.Module, 6, 10),
        (
            "qiime feature-table summarize --p-s<CURSOR>",
            "--p-sample-metadata",
            types.CompletionItemKind.Field,
            30,
            35,
        ),
    ],
)
def test_lsp_completion_replaces_only_prefix(
    catalog: QiimeCatalog,
    source: str,
    label: str,
    kind: types.CompletionItemKind,
    start: int,
    end: int,
) -> None:
    text, offset = extract_cursor_offset(text_with_cursor=source)
    result = handle_completion(
        analyze_document(text),
        types.Position(0, offset),
        lambda: catalog,
    )
    item = next(item for item in result.items if item.label == label)
    assert item.kind == kind
    assert item.text_edit == types.TextEdit(
        range=types.Range(start=types.Position(0, start), end=types.Position(0, end)),
        new_text=label,
    )


@pytest.mark.parametrize(
    "source",
    [
        "echo 😀; qiime feat<CURSOR>",
        'qiime "feat<CURSOR>"',
        "qiime 'feat<CURSOR>'",
        'qiime "feat"<CURSOR>',
        'qiime "fea\\\nt<CURSOR>"',
        "qiime fea\\\nt<CURSOR>",
        "echo 😀\r\nqiime \\\nfeat<CURSOR>",
    ],
)
def test_completion_edit_applies_to_original_source(
    catalog: QiimeCatalog, source: str
) -> None:
    text, offset = extract_cursor_offset(text_with_cursor=source)
    document = analyze_document(text)
    position = offset_to_position(document, offset)
    result = handle_completion(document, position, lambda: catalog)
    item = next(item for item in result.items if item.label == "feature-table")
    edit = item.text_edit
    assert isinstance(edit, types.TextEdit)
    assert edit.range.start.line == edit.range.end.line == position.line
    start = position_to_offset(document, edit.range.start)
    end = position_to_offset(document, edit.range.end)
    changed = analyze_document(text[:start] + edit.new_text + text[end:])
    assert [token.text for token in changed.commands[0].tokens] == [
        "qiime",
        "feature-table",
    ]


def test_completion_prefix_with_non_bmp_character_uses_utf16() -> None:
    catalog = QiimeCatalog.from_hierarchy({"qiime": {"😀plugin": {}}})
    result = handle_completion(
        analyze_document("qiime 😀"), types.Position(0, 8), lambda: catalog
    )
    assert result.items[0].text_edit == types.TextEdit(
        types.Range(types.Position(0, 6), types.Position(0, 8)), "😀plugin"
    )


def test_later_options_also_count_as_used(catalog: QiimeCatalog) -> None:
    text, offset = extract_cursor_offset(
        text_with_cursor="qiime feature-table summarize --<CURSOR> --i-table table.qza"
    )
    result = handle_completion(
        analyze_document(text),
        types.Position(0, offset),
        lambda: catalog,
    )
    labels = {item.label for item in result.items}
    assert "--i-table" not in labels
    assert "--p-sample-metadata" in labels


@pytest.mark.parametrize("source", ["", "echo hello", "qiime"])
def test_non_completion_context_does_not_load_catalog(source: str) -> None:
    def fail_catalog() -> QiimeCatalog:
        raise AssertionError("No catalog is needed outside a completion context")

    result = handle_completion(
        analyze_document(source),
        types.Position(0, len(source)),
        fail_catalog,
    )
    assert result == types.CompletionList(is_incomplete=False, items=[])


@pytest.mark.parametrize(
    ("source", "expected_reads"),
    [
        ("qiime ", []),
        ("qiime feature-table ", []),
        ("qiime feature-table summarize --", [("feature-table", "summarize")]),
    ],
)
def test_only_requested_action_options_are_read(
    catalog: QiimeCatalog,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    expected_reads: list[tuple[str, str]],
) -> None:
    reads: list[tuple[str, str]] = []
    action_options = QiimeCatalog.action_options

    def track(
        self: QiimeCatalog, command: str, action: str
    ) -> tuple[QiimeOptionFact, ...]:
        reads.append((command, action))
        return action_options(self, command, action)

    monkeypatch.setattr(QiimeCatalog, "action_options", track)
    for _ in range(2):
        reads.clear()
        assert complete(source, catalog)
        assert reads == expected_reads
