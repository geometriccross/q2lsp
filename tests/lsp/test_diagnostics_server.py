"""Minimal tests for diagnostics feature in LSP server.

This file tests the debounce manager behavior in isolation.
"""

from __future__ import annotations

import asyncio
import pytest

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
