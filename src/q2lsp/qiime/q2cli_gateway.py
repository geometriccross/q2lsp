"""QIIME2 CLI gateway module.

This module provides a boundary interface for all q2cli interactions,
encapsulating RootCommand creation and hierarchy building logic.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Callable

import click
from q2cli.commands import RootCommand
from q2lsp.qiime.command_hierarchy import build_command_hierarchy
from q2lsp.qiime.types import CommandHierarchy

__all__ = [
    "Q2CliGateway",
    "build_qiime_hierarchy_via_gateway",
    "create_qiime_help_provider",
]


def _sanitize_help_text(text: str) -> str:
    """
    Sanitize help text by removing control characters and ANSI escape sequences.

    Removes:
    - ANSI escape sequences (e.g., \\x1b[31m, \\x1b[0m)
    - ASCII control characters except \\n and \\t
    - \\r characters (and normalizes CRLF to LF)

    Preserves:
    - Newlines (\\n)
    - Tabs (\\t)
    - Indentation

    Args:
        text: Raw help text from command.get_help()

    Returns:
        Sanitized help text safe for LSP hover display.
    """
    # Remove ANSI escape sequences
    # Matches: ESC[ followed by any characters until m or K
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*[mK]")
    text = ansi_pattern.sub("", text)

    # Remove CRLF (normalize to LF)
    text = text.replace("\r\n", "\n")

    # Remove any remaining \r characters
    text = text.replace("\r", "")

    # Remove all ASCII control characters except \n and \t
    # Control chars are in range 0x00-0x1F, plus 0x7F (DEL)
    # We want to keep 0x0A (\n) and 0x09 (\t)
    result = []
    for char in text:
        code = ord(char)
        if (code < 32 and code not in (9, 10)) or code == 127:
            continue
        result.append(char)
    return "".join(result)


class Q2CliGateway:
    """Gateway for QIIME2 CLI interactions.

    Provides a clean interface for building command hierarchies from q2cli,
    with built-in logging and error handling.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Initialize the gateway.

        Args:
            logger: Optional logger instance. If None, creates a default logger.
        """
        if logger is None:
            logger = logging.getLogger("q2lsp.qiime.q2cli_gateway")
        self._logger = logger

    def build_hierarchy(self) -> CommandHierarchy:
        """Build the QIIME2 command hierarchy.

        Logs start, duration, and end of the build process.
        Logs errors if the build fails.

        Returns:
            CommandHierarchy: The built hierarchy structure.

        Raises:
            Exception: Propagates any errors from the build process.
        """
        self._logger.debug("Starting QIIME2 hierarchy build")
        start_time = time.time()

        try:
            hierarchy = self._build_hierarchy_impl()
            duration_ms = (time.time() - start_time) * 1000
            self._logger.debug(
                "QIIME2 hierarchy build completed successfully in %.2fms",
                duration_ms,
            )
            return hierarchy
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._logger.error(
                "QIIME2 hierarchy build failed after %.2fms: %s",
                duration_ms,
                e,
                exc_info=True,
            )
            raise

    def _build_hierarchy_impl(self) -> CommandHierarchy:
        """Internal implementation of hierarchy building.

        This method contains the actual q2cli interaction logic.

        Returns:
            CommandHierarchy: The built hierarchy structure.
        """
        root = RootCommand()
        return build_command_hierarchy(root)


# Singleton gateway instance for backward compatibility
_default_gateway = Q2CliGateway()


def build_qiime_hierarchy_via_gateway() -> CommandHierarchy:
    """Build QIIME2 command hierarchy using the gateway.

    This is the public entry point for building hierarchies.
    It uses the default gateway instance.

    Returns:
        CommandHierarchy: The built hierarchy structure.
    """
    return _default_gateway.build_hierarchy()


# Singleton root command instance for lazy loading
_cached_root_command: RootCommand | None = None
_root_command_lock = threading.Lock()


def _get_root_command() -> RootCommand:
    """Get or create the cached RootCommand instance (thread-safe)."""
    global _cached_root_command
    if _cached_root_command is None:
        with _root_command_lock:
            # Double-check pattern
            if _cached_root_command is None:
                _cached_root_command = RootCommand()
    return _cached_root_command


def create_qiime_help_provider(
    *, max_content_width: int = 80, color: bool = False
) -> Callable[[list[str]], str | None]:
    """
    Create a help provider function for QIIME2 commands.

    The returned function uses click.Context to generate help text that
    matches the CLI output of `qiime ... --help`.

    Args:
        max_content_width: Maximum line width for help text (default: 80).
        color: Whether to include ANSI color codes (default: False).

    Returns:
        A callable that takes a command path and returns help text, or None.
    """

    def _get_help(command_path: list[str]) -> str | None:
        """Get help text for the given command path."""
        root = _get_root_command()
        # Build context chain with parent references for correct Usage lines
        ctx = click.Context(
            root,
            max_content_width=max_content_width,
            color=color,
            info_name="qiime",
        )

        # Navigate to the command
        cmd: click.Command = root
        for name in command_path:
            if isinstance(cmd, click.MultiCommand):
                subcommand = cmd.get_command(ctx, name)
                if subcommand is None:
                    return None
                cmd = subcommand
                # Create new context with parent reference for proper command path
                ctx = click.Context(
                    cmd,
                    parent=ctx,
                    max_content_width=max_content_width,
                    color=color,
                    info_name=name,
                )
            else:
                return None

        # Generate and return help text (sanitized)
        help_text = cmd.get_help(ctx)
        return _sanitize_help_text(help_text)

    return _get_help
