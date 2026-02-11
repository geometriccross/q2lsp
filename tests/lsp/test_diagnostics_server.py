"""Tests for diagnostics feature in LSP server.

Covers debounce manager behavior and diagnostic severity mapping.
"""

from __future__ import annotations

import asyncio
import pytest
from lsprotocol import types

import q2lsp.lsp.server as server_mod
from q2lsp.qiime.types import CommandHierarchy
from q2lsp.lsp.diagnostics.debounce import DebounceManager


class TestDebounceManager:
    """Tests for debounce manager."""

    @pytest.mark.asyncio
    async def test_schedule_and_cancel(self) -> None:
        """Test that scheduling cancels previous task."""
        manager = DebounceManager()
        call_count = 0

        async def func() -> None:
            nonlocal call_count
            call_count += 1

        # Schedule first task
        await manager.schedule("uri1", func, delay_ms=10)

        # Schedule second task immediately (should cancel first)
        await manager.schedule("uri1", func, delay_ms=10)

        # Wait for debounce
        await asyncio.sleep(0.1)

        # Only the second task should execute
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_different_uris_independent(self) -> None:
        """Test that different URIs have independent tasks."""
        manager = DebounceManager()
        calls = []

        async def func1() -> None:
            calls.append("func1")

        async def func2() -> None:
            calls.append("func2")

        # Schedule tasks for different URIs
        await manager.schedule("uri1", func1, delay_ms=10)
        await manager.schedule("uri2", func2, delay_ms=10)

        # Wait for debounce
        await asyncio.sleep(0.1)

        # Both tasks should execute
        assert "func1" in calls
        assert "func2" in calls

    @pytest.mark.asyncio
    async def test_cancel_pending_task(self) -> None:
        """Test that cancel stops a pending task."""
        manager = DebounceManager()
        call_count = 0

        async def func() -> None:
            nonlocal call_count
            call_count += 1

        # Schedule task
        await manager.schedule("uri1", func, delay_ms=100)

        # Cancel before debounce completes
        await manager.cancel("uri1")

        # Wait longer than debounce
        await asyncio.sleep(0.2)

        # Task should not execute
        assert call_count == 0

    @pytest.mark.asyncio
    async def test_exception_handling(self) -> None:
        """Test that exceptions don't crash the manager."""
        manager = DebounceManager()

        async def raising_func() -> None:
            raise RuntimeError("Test error")

        # Schedule a task that raises
        await manager.schedule("uri1", raising_func, delay_ms=10)

        # Wait for debounce - should not raise
        await asyncio.sleep(0.1)


class TestDiagnosticSeverity:
    """Tests for diagnostic severity mapping behavior."""

    @pytest.fixture
    def mock_hierarchy(self) -> CommandHierarchy:
        """Create a hierarchy with required options and one action."""
        return {
            "qiime": {
                "name": "qiime",
                "dummy-plugin": {
                    "type": "plugin",
                    "dummy-action": {
                        "signature": [
                            {
                                "name": "table",
                                "signature_type": "artifact",
                            },
                            {
                                "name": "metadata",
                                "signature_type": "metadata",
                            },
                        ],
                    },
                },
            }
        }

    @pytest.mark.asyncio
    async def test_did_open_publishes_expected_severity_by_diagnostic_code(
        self, mock_hierarchy: CommandHierarchy, mocker
    ) -> None:
        """did_open publishes Error for missing required and Warning for unknown option."""
        server = server_mod.create_server(
            get_hierarchy=lambda: mock_hierarchy,
            debounce_ms=0,
        )

        source = "qiime dummy-plugin dummy-action --unknown-opt value"

        class MockDocument:
            def __init__(self) -> None:
                self.uri = "file:///test.sh"
                self.source = source
                self.version = 1
                self.lines = [source]

        document = MockDocument()

        mock_workspace = mocker.Mock()
        mock_workspace.get_text_document.return_value = document
        server.protocol._workspace = mock_workspace

        mock_publish = mocker.patch.object(
            server,
            "text_document_publish_diagnostics",
            autospec=True,
        )

        fm = server.protocol.fm
        did_open_handler = fm.features[types.TEXT_DOCUMENT_DID_OPEN]
        params = types.DidOpenTextDocumentParams(
            text_document=types.TextDocumentItem(
                uri=document.uri,
                language_id="shellscript",
                version=document.version,
                text=document.source,
            )
        )

        await did_open_handler(params)
        await asyncio.sleep(0.05)

        mock_publish.assert_called_once()
        publish_params = mock_publish.call_args[0][0]
        assert isinstance(publish_params, types.PublishDiagnosticsParams)

        diagnostics = publish_params.diagnostics
        missing_required_diagnostics = [
            diagnostic
            for diagnostic in diagnostics
            if diagnostic.code == "q2lsp-dni/missing-required-option"
        ]
        unknown_option_diagnostics = [
            diagnostic
            for diagnostic in diagnostics
            if diagnostic.code == "q2lsp-dni/unknown-option"
        ]

        assert len(missing_required_diagnostics) == 2
        assert len(unknown_option_diagnostics) == 1
        assert all(
            diagnostic.severity == types.DiagnosticSeverity.Error
            for diagnostic in missing_required_diagnostics
        )
        assert all(
            diagnostic.severity == types.DiagnosticSeverity.Warning
            for diagnostic in unknown_option_diagnostics
        )
