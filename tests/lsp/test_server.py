"""Tests for LSP server module."""

from __future__ import annotations

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

    def test_completion_uses_catalog_backed_usecase(
        self, mock_hierarchy: CommandHierarchy, mocker
    ) -> None:
        """Completion converts hierarchy to catalog before querying completions."""
        server = server_mod.create_server(get_hierarchy=lambda: mock_hierarchy)

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
        catalog = mock_get_completions.call_args.args[1]
        assert isinstance(catalog, QiimeCatalog)
        assert (
            catalog.command_names
            == QiimeCatalog.from_hierarchy(mock_hierarchy).command_names
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

    def test_registers_hover_feature(self, mock_hierarchy: CommandHierarchy) -> None:
        """TEXT_DOCUMENT_HOVER is registered."""
        server = server_mod.create_server(get_hierarchy=lambda: mock_hierarchy)
        fm = server.protocol.fm
        assert types.TEXT_DOCUMENT_HOVER in fm.features

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
    async def test_server_has_publish_diagnostics_method(
        self, mock_hierarchy: CommandHierarchy
    ) -> None:
        """Server has text_document_publish_diagnostics method."""
        server = server_mod.create_server(get_hierarchy=lambda: mock_hierarchy)
        assert hasattr(server, "text_document_publish_diagnostics")

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
