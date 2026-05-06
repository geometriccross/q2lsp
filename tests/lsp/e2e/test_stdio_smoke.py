"""E2E smoke tests for LSP server via stdio."""

from __future__ import annotations

import asyncio

import pytest

from tests.lsp.e2e.lsp_client import LspTestClient


@pytest.mark.e2e
class TestStdioE2E:
    """End-to-end tests for LSP server communication."""

    @pytest.mark.asyncio
    async def test_initialize_shutdown(
        self,
        lsp_client: LspTestClient,
        lsp_server_process: asyncio.subprocess.Process,
    ) -> None:
        """Server responds to initialize and shutdown requests."""
        # Initialize
        response = await lsp_client.initialize()

        assert "result" in response
        assert "capabilities" in response["result"]

        # Shutdown
        shutdown_response = await lsp_client.shutdown_exit()
        assert shutdown_response.get("result") is None
        await asyncio.wait_for(lsp_server_process.wait(), timeout=5.0)
        assert lsp_server_process.returncode == 0

    @pytest.mark.asyncio
    async def test_initialize_does_not_negotiate_utf8_positions(
        self, lsp_client: LspTestClient
    ) -> None:
        """Server keeps wire positions compatible with the UTF-16 adapter."""
        response = await lsp_client.initialize(
            capabilities={"general": {"positionEncodings": ["utf-8", "utf-16"]}}
        )

        assert "result" in response
        capabilities = response["result"]["capabilities"]
        assert capabilities.get("positionEncoding") == "utf-16"

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
            text="qiime feature-table summarize ",
        )

        # Request completion at position after "qiime "
        response = await lsp_client.completion(uri=uri, line=0, character=6)

        assert "result" in response
        result = response["result"]

        # Result should be a CompletionList
        assert "items" in result
        assert isinstance(result["items"], list)

        labels = {item["label"] for item in result["items"]}
        assert {"info", "tools", "feature-table"}.issubset(labels)
        assert "plugins" not in labels

        response = await lsp_client.completion(
            uri=uri, line=0, character=len("qiime feature-table ")
        )
        labels = {item["label"] for item in response["result"]["items"]}
        assert "summarize" in labels

        response = await lsp_client.completion(
            uri=uri, line=0, character=len("qiime feature-table summarize ")
        )
        labels = {item["label"] for item in response["result"]["items"]}
        assert {"--i-table", "--p-sample-metadata", "--o-visualization"}.issubset(
            labels
        )

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
        assert "error" not in response
        assert response["result"]["items"] == []

        await lsp_client.shutdown_exit()
