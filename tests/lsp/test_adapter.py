"""Tests for LSP adapter module."""

from __future__ import annotations

import pytest
from lsprotocol import types
from pygls.workspace import TextDocument

from q2lsp.core.types import (
    CompletionKind,
    CompletionItem as InternalCompletionItem,
)
from q2lsp.lsp.adapter import (
    LSP_POSITION_ENCODING,
    completion_kind_to_lsp,
    offset_to_position,
    position_to_offset,
    to_lsp_completion_item,
)


def test_lsp_position_encoding_contract_is_utf16() -> None:
    """Adapter-owned LSP position mapping contract is UTF-16."""
    assert LSP_POSITION_ENCODING == types.PositionEncodingKind.Utf16


class TestPositionToOffset:
    """Tests for position_to_offset function."""

    @pytest.fixture
    def single_line_doc(self) -> TextDocument:
        """Create a single-line document."""
        return TextDocument(
            uri="file:///test.txt",
            source="qiime info",
            language_id="shell",
            version=1,
        )

    @pytest.fixture
    def multi_line_doc(self) -> TextDocument:
        """Create a multi-line document."""
        return TextDocument(
            uri="file:///test.txt",
            source="abc\ndef\n",
            language_id="shell",
            version=1,
        )

    def test_single_line_start(self, single_line_doc: TextDocument) -> None:
        """Position(0,0) on "qiime info" -> offset 0."""
        pos = types.Position(line=0, character=0)
        offset = position_to_offset(single_line_doc, pos)
        assert offset == 0

    def test_single_line_middle(self, single_line_doc: TextDocument) -> None:
        """Position(0,5) on "qiime info" -> offset 5."""
        pos = types.Position(line=0, character=5)
        offset = position_to_offset(single_line_doc, pos)
        assert offset == 5

    def test_single_line_end(self, single_line_doc: TextDocument) -> None:
        """Position(0,10) on "qiime info" -> offset 10."""
        pos = types.Position(line=0, character=10)
        offset = position_to_offset(single_line_doc, pos)
        assert offset == 10

    def test_multi_line_first_line(self, multi_line_doc: TextDocument) -> None:
        """Position(0,3) on "abc\ndef\n" -> offset 3."""
        pos = types.Position(line=0, character=3)
        offset = position_to_offset(multi_line_doc, pos)
        assert offset == 3

    def test_multi_line_second_line_start(self, multi_line_doc: TextDocument) -> None:
        """Position(1,0) on "abc\ndef\n" -> offset 4."""
        pos = types.Position(line=1, character=0)
        offset = position_to_offset(multi_line_doc, pos)
        assert offset == 4

    def test_multi_line_second_line_middle(self, multi_line_doc: TextDocument) -> None:
        """Position(1,2) on "abc\ndef\n" -> offset 6."""
        pos = types.Position(line=1, character=2)
        offset = position_to_offset(multi_line_doc, pos)
        assert offset == 6

    def test_empty_document(self) -> None:
        """Position(0,0) on "" -> offset 0."""
        doc = TextDocument(
            uri="file:///test.txt",
            source="",
            language_id="shell",
            version=1,
        )
        pos = types.Position(line=0, character=0)
        offset = position_to_offset(doc, pos)
        assert offset == 0

    def test_position_beyond_line_length(self) -> None:
        """Position(0,100) on "abc" -> offset 3 (clamped)."""
        doc = TextDocument(
            uri="file:///test.txt",
            source="abc",
            language_id="shell",
            version=1,
        )
        pos = types.Position(line=0, character=100)
        offset = position_to_offset(doc, pos)
        assert offset == 3

    def test_position_beyond_document_lines(self) -> None:
        """Position(99,0) on "abc\n" -> clamped to end."""
        doc = TextDocument(
            uri="file:///test.txt",
            source="abc\n",
            language_id="shell",
            version=1,
        )
        pos = types.Position(line=99, character=0)
        offset = position_to_offset(doc, pos)
        assert offset == 4

    def test_position_to_offset_clamps_large_character_before_crlf(self) -> None:
        """Position(0,99) on "abc\r\ndef" -> offset 3, before CRLF."""
        doc = TextDocument(
            uri="file:///test.txt",
            source="abc\r\ndef",
            language_id="shell",
            version=1,
        )
        pos = types.Position(line=0, character=99)
        offset = position_to_offset(doc, pos)
        assert offset == 3

    def test_position_to_offset_clamps_large_character_before_cr(self) -> None:
        """Position(0,99) on "abc\rdef" -> offset 3, before CR."""
        doc = TextDocument(
            uri="file:///test.txt",
            source="abc\rdef",
            language_id="shell",
            version=1,
        )
        pos = types.Position(line=0, character=99)
        offset = position_to_offset(doc, pos)
        assert offset == 3

    def test_position_to_offset_handles_utf16_emoji_via_offset_mapper(self) -> None:
        """Position(0,3) on "a😀b" -> offset 2 in Python code points."""
        doc = TextDocument(
            uri="file:///test.txt",
            source="a😀b",
            language_id="shell",
            version=1,
        )

        assert position_to_offset(doc, types.Position(line=0, character=3)) == 2


class TestOffsetToPosition:
    """Tests for offset_to_position function."""

    def test_offset_to_position_handles_utf16_emoji_via_offset_mapper(self) -> None:
        """Offset 2 on "a😀b" -> Position(0,3) in LSP UTF-16 units."""
        doc = TextDocument(
            uri="file:///test.txt",
            source="a😀b",
            language_id="shell",
            version=1,
        )
        position = offset_to_position(doc, 2)
        assert position == types.Position(line=0, character=3)

    def test_offset_to_position_handles_bare_cr_line_break(self) -> None:
        """Bare CR is a line break, with CR offset mapped to previous line end."""
        doc = TextDocument(
            uri="file:///test.txt",
            source="abc\rdef",
            language_id="shell",
            version=1,
        )

        assert offset_to_position(doc, 3) == types.Position(line=0, character=3)
        assert offset_to_position(doc, 4) == types.Position(line=1, character=0)

    def test_offset_to_position_handles_crlf_boundary_offsets(self) -> None:
        """CRLF boundary offsets map to previous EOL until after LF."""
        doc = TextDocument(
            uri="file:///test.txt",
            source="abc\r\ndef",
            language_id="shell",
            version=1,
        )

        assert offset_to_position(doc, 3) == types.Position(line=0, character=3)
        assert offset_to_position(doc, 4) == types.Position(line=0, character=3)
        assert offset_to_position(doc, 5) == types.Position(line=1, character=0)


class TestCompletionKindToLsp:
    """Tests for completion_kind_to_lsp function."""

    def test_plugin_maps_to_module(self) -> None:
        """CompletionKind.PLUGIN -> CompletionItemKind.Module."""
        kind = completion_kind_to_lsp(CompletionKind.PLUGIN)
        assert kind == types.CompletionItemKind.Module

    def test_action_maps_to_function(self) -> None:
        """CompletionKind.ACTION -> CompletionItemKind.Function."""
        kind = completion_kind_to_lsp(CompletionKind.ACTION)
        assert kind == types.CompletionItemKind.Function

    def test_parameter_maps_to_field(self) -> None:
        """CompletionKind.PARAMETER -> CompletionItemKind.Field."""
        kind = completion_kind_to_lsp(CompletionKind.PARAMETER)
        assert kind == types.CompletionItemKind.Field

    def test_builtin_maps_to_class(self) -> None:
        """CompletionKind.BUILTIN -> CompletionItemKind.Class."""
        kind = completion_kind_to_lsp(CompletionKind.BUILTIN)
        assert kind == types.CompletionItemKind.Class

    def test_unknown_maps_to_text(self) -> None:
        """Unknown completion kinds fall back to plain text."""
        assert completion_kind_to_lsp("unknown") == types.CompletionItemKind.Text


class TestToLspCompletionItem:
    """Tests for to_lsp_completion_item function."""

    def test_converts_all_fields(self) -> None:
        """Check label, detail, kind are converted correctly."""
        item = InternalCompletionItem(
            label="test-label",
            detail="test detail",
            kind=CompletionKind.PLUGIN,
            insert_text=None,
        )
        lsp_item = to_lsp_completion_item(item)
        assert lsp_item.label == "test-label"
        assert lsp_item.detail == "test detail"
        assert lsp_item.kind == types.CompletionItemKind.Module

    def test_insert_text_none_when_not_provided(self) -> None:
        """insert_text=None stays None."""
        item = InternalCompletionItem(
            label="test",
            detail="detail",
            kind=CompletionKind.ACTION,
            insert_text=None,
        )
        lsp_item = to_lsp_completion_item(item)
        assert lsp_item.insert_text is None

    def test_insert_text_preserved_when_provided(self) -> None:
        """insert_text="foo" is preserved."""
        item = InternalCompletionItem(
            label="test",
            detail="detail",
            kind=CompletionKind.ACTION,
            insert_text="foo",
        )
        lsp_item = to_lsp_completion_item(item)
        assert lsp_item.insert_text == "foo"

    def test_text_edit_with_position_and_prefix(self) -> None:
        """Verify text_edit is emitted when position and prefix are provided."""
        item = InternalCompletionItem(
            label="--p-input",
            detail="test detail",
            kind=CompletionKind.PARAMETER,
        )
        lsp_item = to_lsp_completion_item(
            item, position=types.Position(line=0, character=5), prefix="--"
        )
        assert lsp_item.text_edit is not None
        assert isinstance(lsp_item.text_edit, types.TextEdit)
        assert lsp_item.text_edit.new_text == "--p-input"
        assert lsp_item.text_edit.range.start == types.Position(line=0, character=3)
        assert lsp_item.text_edit.range.end == types.Position(line=0, character=5)

    def test_empty_prefix_does_not_emit_text_edit(self) -> None:
        """No prefix means normal insert behavior, not a replacement edit."""
        item = InternalCompletionItem(
            label="feature-table",
            detail="test detail",
            kind=CompletionKind.PLUGIN,
        )

        lsp_item = to_lsp_completion_item(
            item, position=types.Position(line=0, character=6), prefix=""
        )

        assert lsp_item.text_edit is None

    def test_text_edit_start_clamps_to_line_start(self) -> None:
        """Prefix longer than the position clamps replacement start to 0."""
        item = InternalCompletionItem(
            label="qiime",
            detail="test detail",
            kind=CompletionKind.BUILTIN,
        )

        lsp_item = to_lsp_completion_item(
            item, position=types.Position(line=0, character=2), prefix="qiime"
        )

        assert lsp_item.text_edit is not None
        assert isinstance(lsp_item.text_edit, types.TextEdit)
        assert lsp_item.text_edit.range.start == types.Position(line=0, character=0)
        assert lsp_item.text_edit.range.end == types.Position(line=0, character=2)

    def test_text_edit_uses_insert_text_as_new_text(self) -> None:
        """Replacement edit inserts insert_text when it differs from the label."""
        item = InternalCompletionItem(
            label="sample_metadata",
            detail="test detail",
            kind=CompletionKind.PARAMETER,
            insert_text="--m-sample-metadata-file",
        )

        lsp_item = to_lsp_completion_item(
            item, position=types.Position(line=0, character=4), prefix="--m-"
        )

        assert lsp_item.text_edit is not None
        assert isinstance(lsp_item.text_edit, types.TextEdit)
        assert lsp_item.text_edit.new_text == "--m-sample-metadata-file"

    def test_text_edit_start_after_non_bmp_before_ascii_prefix(self) -> None:
        """Prefix replacement uses UTF-16 position units after earlier emoji."""
        item = InternalCompletionItem(
            label="qiime",
            detail="test detail",
            kind=CompletionKind.BUILTIN,
        )

        lsp_item = to_lsp_completion_item(
            item, position=types.Position(line=0, character=4), prefix="qi"
        )

        assert lsp_item.text_edit is not None
        assert isinstance(lsp_item.text_edit, types.TextEdit)
        assert lsp_item.text_edit.range.start == types.Position(line=0, character=2)
        assert lsp_item.text_edit.range.end == types.Position(line=0, character=4)

    def test_text_edit_prefix_is_ascii_cli_token_text(self) -> None:
        """QIIME CLI prefixes are ASCII tokens; non-BMP prefix math is out of scope."""
        item = InternalCompletionItem(
            label="feature-table",
            detail="test detail",
            kind=CompletionKind.PLUGIN,
        )

        lsp_item = to_lsp_completion_item(
            item, position=types.Position(line=0, character=9), prefix="fea"
        )

        assert lsp_item.text_edit is not None
        assert isinstance(lsp_item.text_edit, types.TextEdit)
        assert lsp_item.text_edit.range.start == types.Position(line=0, character=6)
        assert lsp_item.text_edit.range.end == types.Position(line=0, character=9)
