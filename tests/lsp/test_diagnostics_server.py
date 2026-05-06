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


async def wait_until(assertion, timeout: float = 1.0) -> None:
    """Wait until an assertion passes, then surface the last failure on timeout."""
    deadline = asyncio.get_running_loop().time() + timeout
    last_error: AssertionError | None = None
    while asyncio.get_running_loop().time() < deadline:
        try:
            assertion()
            return
        except AssertionError as error:
            last_error = error
            await asyncio.sleep(0.01)

    if last_error is not None:
        raise last_error


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

        # Only the second task should execute
        await wait_until(lambda: assert_equal(call_count, 1))

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

        # Both tasks should execute
        await wait_until(lambda: assert_in("func1", calls))
        await wait_until(lambda: assert_in("func2", calls))

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

        ran_successfully = asyncio.Event()

        async def successful_func() -> None:
            ran_successfully.set()

        # Schedule a task that raises
        await manager.schedule("uri1", raising_func, delay_ms=10)

        # Wait for debounce - should not raise
        await asyncio.sleep(0.05)

        # The manager should remain usable after swallowing the exception.
        await manager.schedule("uri1", successful_func, delay_ms=10)
        await asyncio.wait_for(ran_successfully.wait(), timeout=1)


def assert_equal(actual, expected) -> None:
    assert actual == expected


def assert_in(item, container) -> None:
    assert item in container


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

        diagnostics_published = asyncio.Event()
        mock_publish = mocker.patch.object(
            server,
            "text_document_publish_diagnostics",
            autospec=True,
            side_effect=lambda _params: diagnostics_published.set(),
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
        await asyncio.wait_for(diagnostics_published.wait(), timeout=1)

        mock_publish.assert_called_once()
        publish_params = mock_publish.call_args[0][0]
        assert isinstance(publish_params, types.PublishDiagnosticsParams)

        diagnostics = publish_params.diagnostics
        assert publish_params.uri == document.uri
        assert publish_params.version == document.version
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
        unknown_option = unknown_option_diagnostics[0]
        assert unknown_option.range == types.Range(
            start=types.Position(line=0, character=32),
            end=types.Position(line=0, character=45),
        )
        assert all(
            diagnostic.severity == types.DiagnosticSeverity.Error
            for diagnostic in missing_required_diagnostics
        )
        assert all(
            diagnostic.severity == types.DiagnosticSeverity.Warning
            for diagnostic in unknown_option_diagnostics
        )

    @pytest.mark.asyncio
    async def test_did_change_publishes_diagnostics(
        self, mock_hierarchy: CommandHierarchy, mocker
    ) -> None:
        """did_change publishes diagnostics for the changed document version."""
        server = server_mod.create_server(
            get_hierarchy=lambda: mock_hierarchy,
            debounce_ms=0,
        )

        source = "qiime dummy-plugin dummy-action --unknown-opt value"

        class MockDocument:
            def __init__(self) -> None:
                self.uri = "file:///test.sh"
                self.source = source
                self.version = 2
                self.lines = [source]

        document = MockDocument()
        mock_workspace = mocker.Mock()
        mock_workspace.get_text_document.return_value = document
        server.protocol._workspace = mock_workspace

        diagnostics_published = asyncio.Event()
        mock_publish = mocker.patch.object(
            server,
            "text_document_publish_diagnostics",
            autospec=True,
            side_effect=lambda _params: diagnostics_published.set(),
        )

        did_change_handler = server.protocol.fm.features[types.TEXT_DOCUMENT_DID_CHANGE]
        params = types.DidChangeTextDocumentParams(
            text_document=types.VersionedTextDocumentIdentifier(
                uri=document.uri,
                version=document.version,
            ),
            content_changes=[],
        )

        await did_change_handler(params)
        await asyncio.wait_for(diagnostics_published.wait(), timeout=1)

        publish_params = mock_publish.call_args[0][0]
        assert publish_params.uri == document.uri
        assert publish_params.version == document.version
        assert publish_params.diagnostics

    @pytest.mark.asyncio
    async def test_valid_command_publishes_empty_diagnostics(
        self, mock_hierarchy: CommandHierarchy, mocker
    ) -> None:
        """A valid command publishes an empty diagnostics list."""
        server = server_mod.create_server(
            get_hierarchy=lambda: mock_hierarchy,
            debounce_ms=0,
        )

        source = (
            "qiime dummy-plugin dummy-action "
            "--table table.qza --m-metadata metadata.tsv"
        )

        class MockDocument:
            def __init__(self) -> None:
                self.uri = "file:///valid.sh"
                self.source = source
                self.version = 1
                self.lines = [source]

        document = MockDocument()
        mock_workspace = mocker.Mock()
        mock_workspace.get_text_document.return_value = document
        server.protocol._workspace = mock_workspace

        diagnostics_published = asyncio.Event()
        mock_publish = mocker.patch.object(
            server,
            "text_document_publish_diagnostics",
            autospec=True,
            side_effect=lambda _params: diagnostics_published.set(),
        )

        did_open_handler = server.protocol.fm.features[types.TEXT_DOCUMENT_DID_OPEN]
        params = types.DidOpenTextDocumentParams(
            text_document=types.TextDocumentItem(
                uri=document.uri,
                language_id="shellscript",
                version=document.version,
                text=document.source,
            )
        )

        await did_open_handler(params)
        await asyncio.wait_for(diagnostics_published.wait(), timeout=1)

        publish_params = mock_publish.call_args[0][0]
        assert publish_params.uri == document.uri
        assert publish_params.version == document.version
        assert publish_params.diagnostics == []

    @pytest.mark.asyncio
    async def test_diagnostics_reuse_cached_catalog(
        self, mock_hierarchy: CommandHierarchy, mocker
    ) -> None:
        """Repeated diagnostics use the server's cached catalog provider."""
        hierarchy_call_count = 0

        def get_hierarchy() -> CommandHierarchy:
            nonlocal hierarchy_call_count
            hierarchy_call_count += 1
            return mock_hierarchy

        server = server_mod.create_server(
            get_hierarchy=get_hierarchy,
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

        diagnostics_published_count = 0

        def record_publish(_params) -> None:
            nonlocal diagnostics_published_count
            diagnostics_published_count += 1

        mocker.patch.object(
            server,
            "text_document_publish_diagnostics",
            autospec=True,
            side_effect=record_publish,
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
        await wait_until(lambda: assert_equal(diagnostics_published_count, 1))
        await did_open_handler(params)
        await wait_until(lambda: assert_equal(diagnostics_published_count, 2))

        assert hierarchy_call_count == 1

    @pytest.mark.asyncio
    async def test_line_continuation_diagnostic_range_maps_to_original_line(
        self, mocker
    ) -> None:
        """Diagnostics from merged commands publish ranges in original source."""
        hierarchy: CommandHierarchy = {
            "qiime": {
                "name": "qiime",
                "feature-table": {
                    "name": "feature-table",
                    "summarize": {"name": "summarize", "signature": []},
                },
            }
        }
        server = server_mod.create_server(
            get_hierarchy=lambda: hierarchy,
            debounce_ms=0,
        )
        source = "qiime \\\nfeature-tabel summarize"

        class MockDocument:
            def __init__(self) -> None:
                self.uri = "file:///test.sh"
                self.source = source
                self.version = 1

        document = MockDocument()
        mock_workspace = mocker.Mock()
        mock_workspace.get_text_document.return_value = document
        server.protocol._workspace = mock_workspace
        mock_publish = mocker.patch.object(
            server,
            "text_document_publish_diagnostics",
            autospec=True,
        )

        did_open_handler = server.protocol.fm.features[types.TEXT_DOCUMENT_DID_OPEN]
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

        publish_params = mock_publish.call_args[0][0]
        assert isinstance(publish_params, types.PublishDiagnosticsParams)
        assert len(publish_params.diagnostics) == 1
        diagnostic_range = publish_params.diagnostics[0].range
        assert diagnostic_range.start == types.Position(line=1, character=0)
        assert diagnostic_range.end == types.Position(line=1, character=13)
