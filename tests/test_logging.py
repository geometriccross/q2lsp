"""Tests for logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path

from q2lsp.logging import configure_logging, get_logger


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
