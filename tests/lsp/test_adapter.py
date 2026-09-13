"""Wire coordinate and completion conversion contracts."""

from __future__ import annotations

import pytest
from lsprotocol import types

from q2lsp.core.document import analyze_document
from q2lsp.core.types import CompletionItem, CompletionKind
from q2lsp.lsp.adapter import (
    completion_kind_to_lsp,
    merged_range,
    offset_to_position,
    position_to_offset,
    to_lsp_completion_item,
)


@pytest.mark.parametrize(
    ("source", "line", "character", "offset"),
    [
        ("qiime info", 0, 0, 0),
        ("qiime info", 0, 5, 5),
        ("qiime info", 0, 10, 10),
        ("abc\ndef\n", 0, 3, 3),
        ("abc\ndef\n", 1, 0, 4),
        ("abc\ndef\n", 1, 2, 6),
        ("", 0, 0, 0),
        ("abc", 0, 100, 3),
        ("abc\n", 99, 0, 4),
        ("abc\r\ndef", 0, 99, 3),
        ("abc\rdef", 0, 99, 3),
        ("a😀b", 0, 3, 2),
    ],
)
def test_position_to_offset(
    source: str, line: int, character: int, offset: int
) -> None:
    assert (
        position_to_offset(analyze_document(source), types.Position(line, character))
        == offset
    )


@pytest.mark.parametrize(
    ("source", "offset", "line", "character"),
    [
        ("a😀b", 2, 0, 3),
        ("abc\rdef", 3, 0, 3),
        ("abc\rdef", 4, 1, 0),
        ("abc\r\ndef", 3, 0, 3),
        ("abc\r\ndef", 4, 0, 3),
        ("abc\r\ndef", 5, 1, 0),
    ],
)
def test_offset_to_position(
    source: str, offset: int, line: int, character: int
) -> None:
    assert offset_to_position(analyze_document(source), offset) == types.Position(
        line, character
    )


def test_merged_range_maps_both_endpoints_before_utf16_conversion() -> None:
    document = analyze_document("echo 😀; qiime\\\n info")
    token = document.commands[0].tokens[0]
    assert merged_range(document, token.start, token.end) == types.Range(
        start=types.Position(0, 9), end=types.Position(0, 14)
    )
    token = document.commands[0].tokens[1]
    assert merged_range(document, token.start, token.end) == types.Range(
        start=types.Position(1, 1), end=types.Position(1, 5)
    )


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (CompletionKind.PLUGIN, types.CompletionItemKind.Module),
        (CompletionKind.ACTION, types.CompletionItemKind.Function),
        (CompletionKind.PARAMETER, types.CompletionItemKind.Field),
        (CompletionKind.BUILTIN, types.CompletionItemKind.Class),
        ("unknown", types.CompletionItemKind.Text),
    ],
)
def test_completion_kind(
    kind: CompletionKind | str, expected: types.CompletionItemKind
) -> None:
    assert completion_kind_to_lsp(kind) == expected


@pytest.mark.parametrize("insert_text", [None, "", "--p-input"])
def test_completion_fields(insert_text: str | None) -> None:
    item = CompletionItem("label", "detail", CompletionKind.PLUGIN, insert_text)
    result = to_lsp_completion_item(item)
    assert result.label == "label"
    assert result.detail == "detail"
    assert result.kind == types.CompletionItemKind.Module
    assert result.insert_text == (insert_text or None)
    assert result.text_edit is None


@pytest.mark.parametrize("insert_text", [None, "--m-sample-metadata-file"])
def test_completion_edit_uses_explicit_source_range(insert_text: str | None) -> None:
    item = CompletionItem("--p-input", "detail", CompletionKind.PARAMETER, insert_text)
    edit_range = types.Range(types.Position(0, 3), types.Position(0, 5))
    result = to_lsp_completion_item(item, edit_range)
    assert result.text_edit == types.TextEdit(
        range=edit_range, new_text=insert_text or item.label
    )


def test_completion_edit_preserves_prefix_on_previous_line() -> None:
    item = CompletionItem("feature-table", "detail", CompletionKind.PLUGIN)
    edit_range = types.Range(types.Position(1, 0), types.Position(1, 1))
    result = to_lsp_completion_item(item, edit_range, retained_prefix="fea")
    assert result.text_edit == types.TextEdit(range=edit_range, new_text="ture-table")
