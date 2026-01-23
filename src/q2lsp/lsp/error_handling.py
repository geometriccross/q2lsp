"""Error handling utilities for LSP feature handlers."""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def wrap_handler(
    *,
    logger: logging.Logger,
    feature_name: str,
    default_factory: Callable[[], R],
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator that wraps an LSP feature handler with error handling.

    Catches exceptions, logs them, and returns a default value to prevent
    the LSP server from crashing.

    Args:
        logger: Logger instance for error logging.
        feature_name: Name of the LSP feature (for error messages).
        default_factory: Callable that returns a default value on error.

    Returns:
        Decorator function.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return func(*args, **kwargs)
            except Exception:
                logger.exception("Error in %s handler", feature_name)
                return default_factory()

        return wrapper

    return decorator


def wrap_async_handler(
    *,
    logger: logging.Logger,
    feature_name: str,
    default_factory: Callable[[], R],
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Decorator that wraps an async LSP feature handler with error handling.

    Catches exceptions (except CancelledError), logs them, and returns a
    default value to prevent the LSP server from crashing.

    Args:
        logger: Logger instance for error logging.
        feature_name: Name of the LSP feature (for error messages).
        default_factory: Callable that returns a default value on error.

    Returns:
        Decorator function.
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return await func(*args, **kwargs)
            except asyncio.CancelledError:
                # Re-raise cancellation to allow proper request cancellation
                raise
            except Exception:
                logger.exception("Error in %s handler", feature_name)
                return default_factory()

        return wrapper

    return decorator
