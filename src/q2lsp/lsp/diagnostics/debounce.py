"""Debounce manager for diagnostics validation.

Manages async tasks to debounce diagnostic validation per document.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


class DebounceManager:
    """Manages debounced validation tasks per document URI."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def schedule(
        self,
        uri: str,
        func: Callable[[], Awaitable[None]],
        delay_ms: int = 400,
    ) -> None:
        """
        Schedule a validation task with debounce.

        Cancels any existing task for the URI and schedules a new one.

        Args:
            uri: The document URI.
            func: The async function to call after debounce.
            delay_ms: Debounce delay in milliseconds.
        """
        async with self._lock:
            # Cancel existing task for this URI
            if uri in self._tasks:
                old_task = self._tasks[uri]
                if not old_task.done():
                    old_task.cancel()
                    try:
                        await old_task
                    except asyncio.CancelledError:
                        pass

            # Create and schedule new task
            task = asyncio.create_task(self._debounced_call(func, delay_ms))
            self._tasks[uri] = task

    async def cancel(self, uri: str) -> None:
        """
        Cancel any pending task for the URI.

        Args:
            uri: The document URI.
        """
        async with self._lock:
            if uri in self._tasks:
                task = self._tasks[uri]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                del self._tasks[uri]

    async def _debounced_call(
        self, func: Callable[[], Awaitable[None]], delay_ms: int
    ) -> None:
        """
        Call func after delay, handling cancellation.

        Args:
            func: The function to call.
            delay_ms: Delay in milliseconds.
        """
        try:
            await asyncio.sleep(delay_ms / 1000)
            await func()
        except asyncio.CancelledError:
            # Task was cancelled, silently exit
            raise
        except Exception:
            # Log error but don't crash
            # The server-level handler should log this
            pass
