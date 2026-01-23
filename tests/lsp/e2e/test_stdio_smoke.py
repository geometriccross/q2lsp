"""E2E smoke tests for LSP server via stdio."""

from __future__ import annotations

import pytest

from tests.lsp.e2e.lsp_client import LspTestClient


@pytest.mark.e2e
class TestStdioE2E:
    """End-to-end tests for LSP server communication."""

    @pytest.mark.asyncio
    async def test_initialize_shutdown(self, lsp_client: LspTestClient) -> None:
        """Server responds to initialize and shutdown requests."""
        # Initialize
        response = await lsp_client.initialize()

        assert "result" in response
        assert "capabilities" in response["result"]

        # Shutdown
        await lsp_client.shutdown_exit()

    @pytest.mark.asyncio
    async def test_completion_roundtrip(self, lsp_client: LspTestClient) -> None:
        """Server returns completion items for a document."""
        # Initialize
        await lsp_client.initialize()

        # Open a document
        uri = "file:///test.sh"
        await lsp_client.did_open(
            uri=uri,
            language_id="shellscript",
            version=1,
            text="qiime ",
        )

        # Request completion at position after "qiime "
        response = await lsp_client.completion(uri=uri, line=0, character=6)

        assert "result" in response
        result = response["result"]

        # Result should be a CompletionList
        assert "items" in result
        assert isinstance(result["items"], list)

        # Should have some completion items (builtins and plugins from stub)
        assert len(result["items"]) > 0

        # Shutdown
        await lsp_client.shutdown_exit()

    @pytest.mark.asyncio
    async def test_completion_empty_document(self, lsp_client: LspTestClient) -> None:
        """Server handles completion in empty document gracefully."""
        await lsp_client.initialize()

        uri = "file:///empty.sh"
        await lsp_client.did_open(
            uri=uri,
            language_id="shellscript",
            version=1,
            text="",
        )

        response = await lsp_client.completion(uri=uri, line=0, character=0)

        assert "result" in response
        # Empty document should return empty or no completions (not an error)
        assert "items" in response["result"]

        await lsp_client.shutdown_exit()
