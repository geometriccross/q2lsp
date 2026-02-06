"""Tests for LSP server module."""

from __future__ import annotations

import pytest
from lsprotocol import types

import q2lsp.lsp.server as server_mod
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

    def test_registers_hover_feature(self, mock_hierarchy: CommandHierarchy) -> None:
        """TEXT_DOCUMENT_HOVER is registered."""
        server = server_mod.create_server(get_hierarchy=lambda: mock_hierarchy)
        fm = server.protocol.fm
        assert types.TEXT_DOCUMENT_HOVER in fm.features

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
