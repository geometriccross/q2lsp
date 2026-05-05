"""Tests for LSP server module."""

from __future__ import annotations

import asyncio

import pytest
from lsprotocol import types

import q2lsp.lsp.server as server_mod
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.types import CommandHierarchy


class TestCreateServer:
    """Tests for create_server function."""

    @pytest.fixture
    def mock_hierarchy(self) -> CommandHierarchy:
        """Create a mock hierarchy for testing."""
        return {"plugins": {}}

    def test_returns_language_server(self, mock_hierarchy: CommandHierarchy) -> None:
        """Returns LanguageServer instance."""
        server = server_mod.create_server(get_hierarchy=lambda: mock_hierarchy)
        assert isinstance(server, server_mod.LanguageServer)

    def test_registers_completion_feature(
        self, mock_hierarchy: CommandHierarchy
    ) -> None:
        """TEXT_DOCUMENT_COMPLETION is registered."""
        server = server_mod.create_server(get_hierarchy=lambda: mock_hierarchy)
        fm = server.protocol.fm
        assert types.TEXT_DOCUMENT_COMPLETION in fm.features

    def test_completion_trigger_characters(
        self, mock_hierarchy: CommandHierarchy
    ) -> None:
        """Trigger chars are [" ", "-"]."""
        server = server_mod.create_server(get_hierarchy=lambda: mock_hierarchy)
        fm = server.protocol.fm
        completion_options = fm.feature_options[types.TEXT_DOCUMENT_COMPLETION]
        assert completion_options.trigger_characters == [" ", "-"]

    def test_completion_uses_catalog_backed_usecase(self, mocker) -> None:
        """Completion converts hierarchy to catalog before querying completions."""
        hierarchy: CommandHierarchy = {
            "qiime": {
                "name": "qiime",
                "help": "QIIME root help",
                "builtins": [],
                "feature-table": {
                    "name": "feature-table",
                    "short_description": "Feature table plugin",
                },
            }
        }
        server = server_mod.create_server(get_hierarchy=lambda: hierarchy)

        class MockDocument:
            uri = "file:///test.sh"
            source = "qiime "
            version = 1

        mock_workspace = mocker.Mock()
        mock_workspace.get_text_document.return_value = MockDocument()
        server.protocol._workspace = mock_workspace

        mock_get_completions = mocker.patch.object(
            server_mod,
            "get_completions",
            autospec=True,
            return_value=[],
        )

        completion_handler = server.protocol.fm.features[types.TEXT_DOCUMENT_COMPLETION]
        params = types.CompletionParams(
            text_document=types.TextDocumentIdentifier(uri="file:///test.sh"),
            position=types.Position(line=0, character=6),
        )

        completion_handler(params)

        mock_get_completions.assert_called_once()
        request = mock_get_completions.call_args.args[0]
        assert request.mode == "root"
        assert request.prefix == ""
        assert request.command_tokens == ("qiime",)
        catalog = mock_get_completions.call_args.args[1]
        assert isinstance(catalog, QiimeCatalog)
        assert (
            catalog.command_names
            == QiimeCatalog.from_hierarchy(hierarchy).command_names
        )

    def test_completion_and_hover_share_cached_catalog(self, mocker) -> None:
        """Completion builds the catalog once; later catalog hover reuses it."""
        hierarchy: CommandHierarchy = {
            "qiime": {
                "name": "qiime",
                "help": "QIIME root help",
                "builtins": [],
                "feature-table": {
                    "name": "feature-table",
                    "short_description": "Feature table plugin",
                },
            }
        }
        calls = 0

        def get_hierarchy() -> CommandHierarchy:
            nonlocal calls
            calls += 1
            return hierarchy

        server = server_mod.create_server(get_hierarchy=get_hierarchy)

        class MockDocument:
            uri = "file:///test.sh"
            source = "qiime "
            version = 1

        mock_workspace = mocker.Mock()
        mock_workspace.get_text_document.return_value = MockDocument()
        server.protocol._workspace = mock_workspace

        completion_handler = server.protocol.fm.features[types.TEXT_DOCUMENT_COMPLETION]
        completion = completion_handler(
            types.CompletionParams(
                text_document=types.TextDocumentIdentifier(uri="file:///test.sh"),
                position=types.Position(line=0, character=6),
            )
        )

        assert [item.label for item in completion.items] == ["feature-table"]

        hover_handler = server.protocol.fm.features[types.TEXT_DOCUMENT_HOVER]
        hover = hover_handler(
            types.HoverParams(
                text_document=types.TextDocumentIdentifier(uri="file:///test.sh"),
                position=types.Position(line=0, character=2),
            )
        )

        assert hover is not None
        assert isinstance(hover.contents, types.MarkupContent)
        assert "QIIME root help" in hover.contents.value
        assert calls == 1

    def test_completion_text_edit_replaces_partial_prefix_only(self, mocker) -> None:
        """Completing "qiime fea" replaces only "fea" with the candidate."""
        hierarchy: CommandHierarchy = {
            "qiime": {
                "name": "qiime",
                "help": "QIIME root help",
                "builtins": [],
                "feature-table": {
                    "name": "feature-table",
                    "short_description": "Feature table plugin",
                },
            }
        }
        server = server_mod.create_server(get_hierarchy=lambda: hierarchy)

        class MockDocument:
            uri = "file:///test.sh"
            source = "qiime fea"
            version = 1

        mock_workspace = mocker.Mock()
        mock_workspace.get_text_document.return_value = MockDocument()
        server.protocol._workspace = mock_workspace

        completion_handler = server.protocol.fm.features[types.TEXT_DOCUMENT_COMPLETION]
        completion = completion_handler(
            types.CompletionParams(
                text_document=types.TextDocumentIdentifier(uri="file:///test.sh"),
                position=types.Position(line=0, character=9),
            )
        )

        assert len(completion.items) == 1
        item = completion.items[0]
        assert item.label == "feature-table"
        assert item.text_edit is not None
        assert isinstance(item.text_edit, types.TextEdit)
        assert item.text_edit.new_text == "feature-table"
        assert item.text_edit.range == types.Range(
            start=types.Position(line=0, character=6),
            end=types.Position(line=0, character=9),
        )

    def test_completion_returns_empty_list_on_handler_failure(self, mocker) -> None:
        """Completion handler failures return the default empty list."""
        server = server_mod.create_server(get_hierarchy=lambda: {"plugins": {}})
        mock_workspace = mocker.Mock()
        mock_workspace.get_text_document.side_effect = RuntimeError("boom")
        server.protocol._workspace = mock_workspace

        completion_handler = server.protocol.fm.features[types.TEXT_DOCUMENT_COMPLETION]
        completion = completion_handler(
            types.CompletionParams(
                text_document=types.TextDocumentIdentifier(uri="file:///test.sh"),
                position=types.Position(line=0, character=0),
            )
        )

        assert completion == types.CompletionList(is_incomplete=False, items=[])

    def test_registers_hover_feature(self, mock_hierarchy: CommandHierarchy) -> None:
        """TEXT_DOCUMENT_HOVER is registered."""
        server = server_mod.create_server(get_hierarchy=lambda: mock_hierarchy)
        fm = server.protocol.fm
        assert types.TEXT_DOCUMENT_HOVER in fm.features

    @pytest.mark.parametrize(
        ("source", "hover_token", "expected"),
        [
            (
                "qiime feature-table summarize",
                "feature-table",
                "Feature table plugin help",
            ),
            (
                "qiime feature-table summarize",
                "summarize",
                "Summarize action help",
            ),
            ("qiime info", "info", "Builtin info help"),
        ],
    )
    def test_hover_handler_returns_catalog_help_for_command_tokens(
        self,
        mocker,
        source: str,
        hover_token: str,
        expected: str,
    ) -> None:
        """Hover handler returns plugin, action, and builtin catalog help."""
        hierarchy: CommandHierarchy = {
            "qiime": {
                "name": "qiime",
                "help": "QIIME root help",
                "builtins": ["info"],
                "info": {
                    "name": "info",
                    "help": "Builtin info help",
                    "type": "builtin",
                },
                "feature-table": {
                    "name": "feature-table",
                    "short_description": "Feature table plugin help",
                    "summarize": {
                        "name": "summarize",
                        "description": "Summarize action help",
                    },
                },
            }
        }
        server = server_mod.create_server(get_hierarchy=lambda: hierarchy)

        class MockDocument:
            uri = "file:///test.sh"
            version = 1

            def __init__(self, document_source: str) -> None:
                self.source = document_source

        mock_workspace = mocker.Mock()
        mock_workspace.get_text_document.return_value = MockDocument(source)
        server.protocol._workspace = mock_workspace

        hover_handler = server.protocol.fm.features[types.TEXT_DOCUMENT_HOVER]
        hover = hover_handler(
            types.HoverParams(
                text_document=types.TextDocumentIdentifier(uri="file:///test.sh"),
                position=types.Position(
                    line=0,
                    character=source.index(hover_token) + 2,
                ),
            )
        )

        assert hover is not None
        assert isinstance(hover.contents, types.MarkupContent)
        assert expected in hover.contents.value

    def test_hover_with_help_provider_does_not_build_catalog(self, mocker) -> None:
        """Hover uses get_help without calling the catalog hierarchy provider."""

        def get_hierarchy() -> CommandHierarchy:
            raise AssertionError("catalog should not be requested")

        server = server_mod.create_server(
            get_hierarchy=get_hierarchy,
            get_help=lambda command_path: "Root help" if not command_path else None,
        )

        class MockDocument:
            uri = "file:///test.sh"
            source = "qiime"
            version = 1

        mock_workspace = mocker.Mock()
        mock_workspace.get_text_document.return_value = MockDocument()
        server.protocol._workspace = mock_workspace

        hover_handler = server.protocol.fm.features[types.TEXT_DOCUMENT_HOVER]
        params = types.HoverParams(
            text_document=types.TextDocumentIdentifier(uri="file:///test.sh"),
            position=types.Position(line=0, character=2),
        )

        hover = hover_handler(params)

        assert hover is not None
        assert isinstance(hover.contents, types.MarkupContent)
        assert "Root help" in hover.contents.value

    def test_registers_did_open(self, mock_hierarchy: CommandHierarchy) -> None:
        """TEXT_DOCUMENT_DID_OPEN is registered."""
        server = server_mod.create_server(get_hierarchy=lambda: mock_hierarchy)
        fm = server.protocol.fm
        assert types.TEXT_DOCUMENT_DID_OPEN in fm.features

    def test_registers_did_change(self, mock_hierarchy: CommandHierarchy) -> None:
        """TEXT_DOCUMENT_DID_CHANGE is registered."""
        server = server_mod.create_server(get_hierarchy=lambda: mock_hierarchy)
        fm = server.protocol.fm
        assert types.TEXT_DOCUMENT_DID_CHANGE in fm.features

    def test_registers_did_close(self, mock_hierarchy: CommandHierarchy) -> None:
        """TEXT_DOCUMENT_DID_CLOSE is registered."""
        server = server_mod.create_server(get_hierarchy=lambda: mock_hierarchy)
        fm = server.protocol.fm
        assert types.TEXT_DOCUMENT_DID_CLOSE in fm.features

    @pytest.mark.asyncio
    async def test_did_close_calls_text_document_publish_diagnostics(
        self, mock_hierarchy: CommandHierarchy, mocker
    ) -> None:
        """did_close publishes empty diagnostics via text_document_publish_diagnostics."""
        server = server_mod.create_server(get_hierarchy=lambda: mock_hierarchy)

        # Mock the text_document_publish_diagnostics method
        mock_publish = mocker.patch.object(
            server,
            "text_document_publish_diagnostics",
            autospec=True,
        )

        # Get the did_close handler from the feature manager
        fm = server.protocol.fm
        did_close_handler = fm.features[types.TEXT_DOCUMENT_DID_CLOSE]

        # Trigger didClose
        uri = "file:///test.sh"
        params = types.DidCloseTextDocumentParams(
            text_document=types.TextDocumentIdentifier(uri=uri)
        )

        # Call the handler
        await did_close_handler(params)

        # Assert text_document_publish_diagnostics was called with empty list
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert isinstance(call_args[0][0], types.PublishDiagnosticsParams)
        assert call_args[0][0].uri == uri
        assert call_args[0][0].diagnostics == []

    @pytest.mark.asyncio
    async def test_did_close_cancels_pending_diagnostics(
        self, mock_hierarchy: CommandHierarchy, mocker
    ) -> None:
        """did_close prevents debounced did_open/did_change diagnostics from publishing."""
        debounce_ms = 20
        server = server_mod.create_server(
            get_hierarchy=lambda: mock_hierarchy,
            debounce_ms=debounce_ms,
        )

        class MockDocument:
            uri = "file:///test.sh"
            source = "qiime not-a-plugin"
            version = 2

        mock_workspace = mocker.Mock()
        mock_workspace.get_text_document.return_value = MockDocument()
        server.protocol._workspace = mock_workspace
        mock_publish = mocker.patch.object(
            server,
            "text_document_publish_diagnostics",
            autospec=True,
        )

        fm = server.protocol.fm
        uri = "file:///test.sh"
        await fm.features[types.TEXT_DOCUMENT_DID_OPEN](
            types.DidOpenTextDocumentParams(
                text_document=types.TextDocumentItem(
                    uri=uri,
                    language_id="shellscript",
                    version=1,
                    text="qiime not-a-plugin",
                )
            )
        )
        await fm.features[types.TEXT_DOCUMENT_DID_CHANGE](
            types.DidChangeTextDocumentParams(
                text_document=types.VersionedTextDocumentIdentifier(uri=uri, version=2),
                content_changes=[],
            )
        )
        await fm.features[types.TEXT_DOCUMENT_DID_CLOSE](
            types.DidCloseTextDocumentParams(
                text_document=types.TextDocumentIdentifier(uri=uri)
            )
        )

        assert mock_publish.call_count == 1
        clearing_publish = mock_publish.call_args.args[0]
        assert clearing_publish.diagnostics == []

        await asyncio.sleep((debounce_ms / 1000) * 2)

        assert mock_publish.call_count == 1
