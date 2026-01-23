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
        get_hierarchy = lambda: mock_hierarchy
        server = server_mod.create_server(get_hierarchy=get_hierarchy)
        assert isinstance(server, server_mod.LanguageServer)

    def test_registers_completion_feature(
        self, mock_hierarchy: CommandHierarchy
    ) -> None:
        """TEXT_DOCUMENT_COMPLETION is registered."""
        get_hierarchy = lambda: mock_hierarchy
        server = server_mod.create_server(get_hierarchy=get_hierarchy)
        fm = server.protocol.fm
        assert types.TEXT_DOCUMENT_COMPLETION in fm.features

    def test_completion_trigger_characters(
        self, mock_hierarchy: CommandHierarchy
    ) -> None:
        """Trigger chars are [" ", "-"]."""
        get_hierarchy = lambda: mock_hierarchy
        server = server_mod.create_server(get_hierarchy=get_hierarchy)
        fm = server.protocol.fm
        completion_options = fm.feature_options[types.TEXT_DOCUMENT_COMPLETION]
        assert completion_options.trigger_characters == [" ", "-"]
