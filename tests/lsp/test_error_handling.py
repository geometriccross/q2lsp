"""Tests for error handling utilities."""

from __future__ import annotations

import asyncio
import logging

import pytest

from q2lsp.lsp.error_handling import wrap_async_handler, wrap_handler


class TestWrapHandler:
    """Tests for wrap_handler decorator."""

    @pytest.fixture
    def logger(self) -> logging.Logger:
        """Create a test logger."""
        return logging.getLogger("q2lsp.test")

    def test_returns_result_on_success(self, logger: logging.Logger) -> None:
        """Handler returns normal result when no exception occurs."""

        @wrap_handler(
            logger=logger,
            feature_name="test/feature",
            default_factory=lambda: "default",
        )
        def handler() -> str:
            return "success"

        result = handler()
        assert result == "success"

    def test_returns_default_on_exception(self, logger: logging.Logger) -> None:
        """Handler returns default value when exception occurs."""

        @wrap_handler(
            logger=logger,
            feature_name="test/feature",
            default_factory=lambda: "default",
        )
        def handler() -> str:
            raise ValueError("test error")

        result = handler()
        assert result == "default"

    def test_logs_exception(
        self, logger: logging.Logger, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Exception is logged with traceback."""

        @wrap_handler(
            logger=logger,
            feature_name="test/feature",
            default_factory=lambda: None,
        )
        def handler() -> None:
            raise ValueError("specific error message")

        with caplog.at_level(logging.ERROR):
            handler()

        assert "test/feature" in caplog.text
        assert "specific error message" in caplog.text

    def test_preserves_function_metadata(self, logger: logging.Logger) -> None:
        """Decorator preserves function name and docstring."""

        @wrap_handler(
            logger=logger,
            feature_name="test/feature",
            default_factory=lambda: None,
        )
        def my_handler() -> None:
            """My docstring."""
            pass

        assert my_handler.__name__ == "my_handler"
        assert my_handler.__doc__ == "My docstring."


class TestWrapAsyncHandler:
    """Tests for wrap_async_handler decorator."""

    @pytest.fixture
    def logger(self) -> logging.Logger:
        """Create a test logger."""
        return logging.getLogger("q2lsp.test")

    @pytest.mark.asyncio
    async def test_returns_result_on_success(self, logger: logging.Logger) -> None:
        """Async handler returns normal result when no exception occurs."""

        @wrap_async_handler(
            logger=logger,
            feature_name="test/feature",
            default_factory=lambda: "default",
        )
        async def handler() -> str:
            return "success"

        result = await handler()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_returns_default_on_exception(self, logger: logging.Logger) -> None:
        """Async handler returns default value when exception occurs."""

        @wrap_async_handler(
            logger=logger,
            feature_name="test/feature",
            default_factory=lambda: "default",
        )
        async def handler() -> str:
            raise ValueError("test error")

        result = await handler()
        assert result == "default"

    @pytest.mark.asyncio
    async def test_reraises_cancelled_error(self, logger: logging.Logger) -> None:
        """CancelledError is re-raised to allow proper cancellation."""

        @wrap_async_handler(
            logger=logger,
            feature_name="test/feature",
            default_factory=lambda: "default",
        )
        async def handler() -> str:
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await handler()

    @pytest.mark.asyncio
    async def test_logs_exception(
        self, logger: logging.Logger, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Exception is logged with traceback."""

        @wrap_async_handler(
            logger=logger,
            feature_name="test/async_feature",
            default_factory=lambda: None,
        )
        async def handler() -> None:
            raise ValueError("async error message")

        with caplog.at_level(logging.ERROR):
            await handler()

        assert "test/async_feature" in caplog.text
        assert "async error message" in caplog.text
