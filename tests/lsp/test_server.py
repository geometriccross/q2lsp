"""Tests for LSP server module."""

from __future__ import annotations

import pytest
from lsprotocol import types
from pygls.workspace import TextDocument

import q2lsp.lsp.server as server_mod
from q2lsp.lsp.completions import CompletionItem as InternalCompletionItem


class TestPositionToOffset:
    """Tests for _position_to_offset function."""

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
        offset = server_mod._position_to_offset(single_line_doc, pos)
        assert offset == 0

    def test_single_line_middle(self, single_line_doc: TextDocument) -> None:
        """Position(0,5) on "qiime info" -> offset 5."""
        pos = types.Position(line=0, character=5)
        offset = server_mod._position_to_offset(single_line_doc, pos)
        assert offset == 5

    def test_single_line_end(self, single_line_doc: TextDocument) -> None:
        """Position(0,10) on "qiime info" -> offset 10."""
        pos = types.Position(line=0, character=10)
        offset = server_mod._position_to_offset(single_line_doc, pos)
        assert offset == 10

    def test_multi_line_first_line(self, multi_line_doc: TextDocument) -> None:
        """Position(0,3) on "abc\ndef\n" -> offset 3."""
        pos = types.Position(line=0, character=3)
        offset = server_mod._position_to_offset(multi_line_doc, pos)
        assert offset == 3

    def test_multi_line_second_line_start(self, multi_line_doc: TextDocument) -> None:
        """Position(1,0) on "abc\ndef\n" -> offset 4."""
        pos = types.Position(line=1, character=0)
        offset = server_mod._position_to_offset(multi_line_doc, pos)
        assert offset == 4

    def test_multi_line_second_line_middle(self, multi_line_doc: TextDocument) -> None:
        """Position(1,2) on "abc\ndef\n" -> offset 6."""
        pos = types.Position(line=1, character=2)
        offset = server_mod._position_to_offset(multi_line_doc, pos)
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
        offset = server_mod._position_to_offset(doc, pos)
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
        offset = server_mod._position_to_offset(doc, pos)
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
        offset = server_mod._position_to_offset(doc, pos)
        assert offset == 4


class TestCompletionKindFromString:
    """Tests for _completion_kind_from_string function."""

    def test_plugin_maps_to_module(self) -> None:
        """ "plugin" -> CompletionItemKind.Module."""
        kind = server_mod._completion_kind_from_string("plugin")
        assert kind == types.CompletionItemKind.Module

    def test_action_maps_to_function(self) -> None:
        """ "action" -> CompletionItemKind.Function."""
        kind = server_mod._completion_kind_from_string("action")
        assert kind == types.CompletionItemKind.Function

    def test_parameter_maps_to_field(self) -> None:
        """ "parameter" -> CompletionItemKind.Field."""
        kind = server_mod._completion_kind_from_string("parameter")
        assert kind == types.CompletionItemKind.Field

    def test_builtin_maps_to_class(self) -> None:
        """ "builtin" -> CompletionItemKind.Class."""
        kind = server_mod._completion_kind_from_string("builtin")
        assert kind == types.CompletionItemKind.Class

    def test_unknown_kind_maps_to_text(self) -> None:
        """ "unknown" -> CompletionItemKind.Text."""
        kind = server_mod._completion_kind_from_string("unknown")
        assert kind == types.CompletionItemKind.Text

    def test_empty_string_maps_to_text(self) -> None:
        """ "" -> CompletionItemKind.Text."""
        kind = server_mod._completion_kind_from_string("")
        assert kind == types.CompletionItemKind.Text


class TestToLspCompletionItem:
    """Tests for _to_lsp_completion_item function."""

    def test_converts_all_fields(self) -> None:
        """Check label, detail, kind are converted correctly."""
        item = InternalCompletionItem(
            label="test-label",
            detail="test detail",
            kind="plugin",
            insert_text=None,
        )
        lsp_item = server_mod._to_lsp_completion_item(item)
        assert lsp_item.label == "test-label"
        assert lsp_item.detail == "test detail"
        assert lsp_item.kind == types.CompletionItemKind.Module

    def test_insert_text_none_when_not_provided(self) -> None:
        """insert_text=None stays None."""
        item = InternalCompletionItem(
            label="test", detail="detail", kind="action", insert_text=None
        )
        lsp_item = server_mod._to_lsp_completion_item(item)
        assert lsp_item.insert_text is None

    def test_insert_text_preserved_when_provided(self) -> None:
        """insert_text="foo" is preserved."""
        item = InternalCompletionItem(
            label="test", detail="detail", kind="action", insert_text="foo"
        )
        lsp_item = server_mod._to_lsp_completion_item(item)
        assert lsp_item.insert_text == "foo"


class TestGetCachedHierarchy:
    """Tests for get_cached_hierarchy caching behavior."""

    def test_builds_hierarchy_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Call twice, _build_hierarchy called only once."""
        # Clear cache
        monkeypatch.setattr(server_mod, "_hierarchy_cache", None)

        # Track calls to _build_hierarchy
        build_calls = 0

        def mock_build() -> dict:
            nonlocal build_calls
            build_calls += 1
            return {"test": "hierarchy"}

        monkeypatch.setattr(server_mod, "_build_hierarchy", mock_build)

        # Call twice
        result1 = server_mod.get_cached_hierarchy()
        result2 = server_mod.get_cached_hierarchy()

        assert build_calls == 1
        assert result1 == result2

    def test_returns_same_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Both calls return same object."""
        # Clear cache
        monkeypatch.setattr(server_mod, "_hierarchy_cache", None)

        hierarchy = {"test": "value"}

        def mock_build() -> dict:
            return hierarchy

        monkeypatch.setattr(server_mod, "_build_hierarchy", mock_build)

        result1 = server_mod.get_cached_hierarchy()
        result2 = server_mod.get_cached_hierarchy()

        assert result1 is result2

    def test_uses_existing_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If cache is pre-set, _build_hierarchy not called."""
        pre_cached = {"cached": "value"}
        monkeypatch.setattr(server_mod, "_hierarchy_cache", pre_cached)

        build_calls = 0

        def mock_build() -> dict:
            nonlocal build_calls
            build_calls += 1
            return {"new": "value"}

        monkeypatch.setattr(server_mod, "_build_hierarchy", mock_build)

        result = server_mod.get_cached_hierarchy()

        assert build_calls == 0
        assert result is pre_cached


class TestCreateServer:
    """Tests for create_server function."""

    def test_returns_language_server(self) -> None:
        """Returns LanguageServer instance."""
        server = server_mod.create_server()
        assert isinstance(server, server_mod.LanguageServer)

    def test_registers_completion_feature(self) -> None:
        """TEXT_DOCUMENT_COMPLETION is registered."""
        server = server_mod.create_server()
        fm = server.protocol.fm
        assert types.TEXT_DOCUMENT_COMPLETION in fm.features

    def test_completion_trigger_characters(self) -> None:
        """Trigger chars are [" ", "-"]."""
        server = server_mod.create_server()
        # The feature registration should have the correct options
        fm = server.protocol.fm
        completion_options = fm.feature_options[types.TEXT_DOCUMENT_COMPLETION]
        assert completion_options.trigger_characters == [" ", "-"]
