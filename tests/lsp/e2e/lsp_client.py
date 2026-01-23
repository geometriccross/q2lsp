"""Minimal LSP client for E2E testing."""

from __future__ import annotations

import asyncio
import json
from typing import Any


async def write_lsp_message(
    writer: asyncio.StreamWriter, payload: dict[str, Any]
) -> None:
    """Write an LSP message with Content-Length header."""
    body = json.dumps(payload).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
    writer.write(header + body)
    await writer.drain()


async def read_lsp_message(
    reader: asyncio.StreamReader,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Read an LSP message, parsing the Content-Length header."""
    # Read headers until empty line
    headers: dict[str, str] = {}
    while True:
        line = await asyncio.wait_for(reader.readline(), timeout=timeout)
        line_str = line.decode("utf-8").strip()
        if not line_str:
            break
        if ":" in line_str:
            key, value = line_str.split(":", 1)
            headers[key.strip()] = value.strip()

    content_length = int(headers.get("Content-Length", "0"))
    if content_length == 0:
        raise ValueError("No Content-Length header in LSP message")

    body = await asyncio.wait_for(reader.readexactly(content_length), timeout=timeout)
    return json.loads(body.decode("utf-8"))


class LspTestClient:
    """Minimal LSP client for testing."""

    def __init__(
        self,
        *,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._request_id = 0

    async def send_request(
        self,
        *,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for response."""
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params

        await write_lsp_message(self._writer, request)
        return await read_lsp_message(self._reader)

    async def send_notification(
        self,
        *,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        notification: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            notification["params"] = params

        await write_lsp_message(self._writer, notification)

    async def initialize(self, *, root_uri: str = "file:///test") -> dict[str, Any]:
        """Send initialize request."""
        response = await self.send_request(
            method="initialize",
            params={
                "processId": None,
                "rootUri": root_uri,
                "capabilities": {},
            },
        )
        # Send initialized notification
        await self.send_notification(method="initialized", params={})
        return response

    async def shutdown_exit(self) -> None:
        """Send shutdown request and exit notification."""
        await self.send_request(method="shutdown")
        await self.send_notification(method="exit")

    async def did_open(
        self,
        *,
        uri: str,
        language_id: str,
        version: int,
        text: str,
    ) -> None:
        """Send textDocument/didOpen notification."""
        await self.send_notification(
            method="textDocument/didOpen",
            params={
                "textDocument": {
                    "uri": uri,
                    "languageId": language_id,
                    "version": version,
                    "text": text,
                }
            },
        )

    async def completion(
        self,
        *,
        uri: str,
        line: int,
        character: int,
    ) -> dict[str, Any]:
        """Send textDocument/completion request."""
        return await self.send_request(
            method="textDocument/completion",
            params={
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
            },
        )
