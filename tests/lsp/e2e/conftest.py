"""Fixtures for E2E tests."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncGenerator

import pytest

from tests.lsp.e2e.lsp_client import LspTestClient


@pytest.fixture
async def lsp_server_process() -> AsyncGenerator[asyncio.subprocess.Process, None]:
    """Start the test LSP server as a subprocess."""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "tests.lsp.e2e.server_entry",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    yield process

    # Cleanup
    if process.returncode is None:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            process.kill()


@pytest.fixture
async def lsp_client(
    lsp_server_process: asyncio.subprocess.Process,
) -> AsyncGenerator[LspTestClient, None]:
    """Create an LSP client connected to the test server."""
    assert lsp_server_process.stdin is not None
    assert lsp_server_process.stdout is not None

    yield LspTestClient(
        reader=lsp_server_process.stdout, writer=lsp_server_process.stdin
    )
