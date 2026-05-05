"""Tests for logging configuration."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from q2lsp.logging import configure_logging, get_logger


@pytest.fixture(autouse=True)
def restore_q2lsp_logger(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Restore global q2lsp logger state after each test."""
    logger = logging.getLogger("q2lsp")
    handlers = list(logger.handlers)
    original_handlers = set(handlers)
    transient_handlers: set[logging.Handler] = set()
    level = logger.level
    propagate = logger.propagate

    original_add_handler = logger.addHandler

    def add_handler(handler: logging.Handler) -> None:
        if handler not in original_handlers:
            transient_handlers.add(handler)
        original_add_handler(handler)

    monkeypatch.setattr(logger, "addHandler", add_handler)

    yield

    for handler in list(logger.handlers):
        if handler not in handlers:
            logger.removeHandler(handler)

    for handler in transient_handlers:
        if handler not in original_handlers:
            handler.close()

    logger.handlers[:] = handlers
    logger.setLevel(level)
    logger.propagate = propagate


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_default_configuration(self) -> None:
        """Default configuration sets INFO level."""
        configure_logging()
        logger = logging.getLogger("q2lsp")
        assert logger.level == logging.INFO

    def test_custom_level(self) -> None:
        """Can set custom log level."""
        configure_logging(level="DEBUG")
        logger = logging.getLogger("q2lsp")
        assert logger.level == logging.DEBUG

    def test_case_insensitive_level(self) -> None:
        """Log level is case insensitive."""
        configure_logging(level="warning")
        logger = logging.getLogger("q2lsp")
        assert logger.level == logging.WARNING

    def test_invalid_level_falls_back_to_info(self) -> None:
        """Unknown log levels fall back to INFO."""
        configure_logging(level="not-a-level")
        logger = logging.getLogger("q2lsp")
        assert logger.level == logging.INFO

    def test_default_stream_writes_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Default stream handler writes log output to stderr."""
        configure_logging()
        logger = logging.getLogger("q2lsp")

        logger.info("stderr message")

        captured = capsys.readouterr()
        assert "stderr message" in captured.err
        assert captured.out == ""

    def test_file_handler(self, tmp_path: Path) -> None:
        """Can configure logging to file."""
        log_file = tmp_path / "test.log"
        configure_logging(log_file=log_file)
        logger = logging.getLogger("q2lsp")

        # Log something and verify it appears in the file
        logger.info("test message")

        # Flush handlers
        for handler in logger.handlers:
            handler.flush()

        assert log_file.exists()
        content = log_file.read_text()
        assert "test message" in content

    def test_clears_existing_handlers(self) -> None:
        """configure_logging clears existing handlers."""
        configure_logging()
        logger = logging.getLogger("q2lsp")
        initial_count = len(logger.handlers)

        # Call again
        configure_logging()

        assert len(logger.handlers) == initial_count

    def test_removes_sentinel_handler(self) -> None:
        """configure_logging removes previously attached handlers."""
        logger = logging.getLogger("q2lsp")
        sentinel = logging.NullHandler()
        logger.addHandler(sentinel)

        configure_logging()

        assert sentinel not in logger.handlers


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_namespaced_logger(self) -> None:
        """get_logger returns logger with q2lsp prefix."""
        logger = get_logger("test")
        assert logger.name == "q2lsp.test"

    def test_nested_namespace(self) -> None:
        """Can create nested logger names."""
        logger = get_logger("lsp.server")
        assert logger.name == "q2lsp.lsp.server"
