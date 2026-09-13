"""E2E smoke tests for LSP server via stdio."""

from __future__ import annotations

import asyncio

import pytest

from tests.lsp.e2e.lsp_client import LspTestClient, read_lsp_message


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
        assert response["result"]["capabilities"]["completionProvider"][
            "triggerCharacters"
        ] == [" ", "-"]

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
    async def test_utf16_incremental_edit_updates_all_feature_snapshots(
        self, lsp_client: LspTestClient
    ) -> None:
        await lsp_client.initialize(
            capabilities={"general": {"positionEncodings": ["utf-8", "utf-16"]}}
        )
        uri = "file:///unicode.sh"
        await lsp_client.did_open(
            uri=uri,
            language_id="shellscript",
            version=1,
            text="echo 😀; qiime feat\r\n",
        )
        before = await lsp_client.completion(uri=uri, line=0, character=19)
        assert [item["label"] for item in before["result"]["items"]] == [
            "feature-table"
        ]
        await lsp_client.send_notification(
            method="textDocument/didChange",
            params={
                "textDocument": {"uri": uri, "version": 2},
                "contentChanges": [
                    {
                        "range": {
                            "start": {"line": 0, "character": 15},
                            "end": {"line": 0, "character": 19},
                        },
                        "text": "feature-table ",
                    }
                ],
            },
        )
        after = await lsp_client.completion(uri=uri, line=0, character=29)
        assert "summarize" in {item["label"] for item in after["result"]["items"]}
        lenses = await lsp_client.code_lens(uri=uri)
        assert lenses["result"][0]["command"]["arguments"][0]["tokens"] == [
            "qiime",
            "feature-table",
        ]
        assert lenses["result"][0]["range"] == {
            "start": {"line": 0, "character": 9},
            "end": {"line": 0, "character": 14},
        }
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

    @pytest.mark.asyncio
    async def test_diagnostics_lifecycle_and_provider_hover(
        self,
        lsp_client: LspTestClient,
        lsp_server_process: asyncio.subprocess.Process,
    ) -> None:
        await lsp_client.initialize()
        reader = lsp_server_process.stdout
        assert reader is not None
        uri = "file:///diagnostics.sh"
        await lsp_client.did_open(
            uri=uri, language_id="shellscript", version=1, text="qiime unknown"
        )
        opened = await read_lsp_message(reader)
        assert opened["method"] == "textDocument/publishDiagnostics"
        assert opened["params"]["version"] == 1
        assert opened["params"]["diagnostics"][0]["code"] == "q2lsp-dni/unknown-root"

        await lsp_client.send_notification(
            method="textDocument/didChange",
            params={
                "textDocument": {"uri": uri, "version": 2},
                "contentChanges": [
                    {
                        "text": (
                            "qiime feature-table summarize --i-table in.qza "
                            "--o-visualization out.qzv --p-sample-metadata metadata.tsv"
                        )
                    }
                ],
            },
        )
        changed = await read_lsp_message(reader)
        assert changed["method"] == "textDocument/publishDiagnostics"
        assert changed["params"]["version"] == 2
        assert changed["params"]["diagnostics"] == []

        hover = await lsp_client.send_request(
            method="textDocument/hover",
            params={
                "textDocument": {"uri": uri},
                "position": {"line": 0, "character": 8},
            },
        )
        assert hover["result"]["contents"] == {
            "kind": "markdown",
            "value": "```\nUsage: qiime feature-table\n```",
        }

        await lsp_client.send_notification(
            method="textDocument/didClose",
            params={"textDocument": {"uri": uri}},
        )
        closed = await read_lsp_message(reader)
        assert closed["method"] == "textDocument/publishDiagnostics"
        assert closed["params"]["uri"] == uri
        assert closed["params"]["diagnostics"] == []
        await lsp_client.shutdown_exit()

    @pytest.mark.asyncio
    async def test_code_lens_roundtrip_returns_run_command_tokens_and_shell_text(
        self, lsp_client: LspTestClient
    ) -> None:
        """Server returns runnable CodeLens items with tokens and shell text."""
        await lsp_client.initialize()

        uri = "file:///run.sh"
        await lsp_client.did_open(
            uri=uri,
            language_id="shellscript",
            version=1,
            text='qiime feature-table summarize --i-table "$TABLE"',
        )

        response = await lsp_client.code_lens(uri=uri)

        assert "result" in response
        assert response["result"] == [
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 5},
                },
                "command": {
                    "title": "Run QIIME command",
                    "command": "q2lsp.runCommand",
                    "arguments": [
                        {
                            "uri": uri,
                            "commandText": 'qiime feature-table summarize --i-table "$TABLE"',
                            "tokens": [
                                "qiime",
                                "feature-table",
                                "summarize",
                                "--i-table",
                                "$TABLE",
                            ],
                        }
                    ],
                },
            }
        ]

        await lsp_client.shutdown_exit()
