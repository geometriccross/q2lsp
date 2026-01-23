"""Tests for LSP adapter module."""

from __future__ import annotations

import pytest
from lsprotocol import types
from pygls.workspace import TextDocument

from q2lsp.lsp.adapter import (
    completion_kind_to_lsp,
    position_to_offset,
    to_lsp_completion_item,
)
from q2lsp.lsp.completions import CompletionItem as InternalCompletionItem
from q2lsp.lsp.types import CompletionKind


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
            label="test", detail="detail", kind=CompletionKind.ACTION, insert_text=None
        )
        lsp_item = to_lsp_completion_item(item)
        assert lsp_item.insert_text is None

    def test_insert_text_preserved_when_provided(self) -> None:
        """insert_text="foo" is preserved."""
        item = InternalCompletionItem(
            label="test", detail="detail", kind=CompletionKind.ACTION, insert_text="foo"
        )
        lsp_item = to_lsp_completion_item(item)
        assert lsp_item.insert_text == "foo"
