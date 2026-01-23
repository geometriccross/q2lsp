"""Logging configuration for q2lsp."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def configure_logging(*, level: str = "INFO", log_file: Path | None = None) -> None:
    """
    Configure logging for q2lsp.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional path to log file. If None, logs to stderr.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Get root logger for q2lsp
    logger = logging.getLogger("q2lsp")
    logger.setLevel(log_level)

    # Clear any existing handlers
    logger.handlers.clear()

    # Add handler based on configuration
    if log_file is not None:
        handler: logging.Handler = logging.FileHandler(log_file)
    else:
        handler = logging.StreamHandler(sys.stderr)

    handler.setFormatter(formatter)
    handler.setLevel(log_level)
    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name under q2lsp namespace.

    Args:
        name: Logger name (will be prefixed with 'q2lsp.').

    Returns:
        Logger instance.
    """
    return logging.getLogger(f"q2lsp.{name}")
