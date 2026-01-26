"""QIIME2 CLI gateway module.

This module provides a boundary interface for all q2cli interactions,
encapsulating RootCommand creation and hierarchy building logic.
"""

from __future__ import annotations

import logging
import time

from q2cli.commands import RootCommand
from q2lsp.qiime.command_hierarchy import build_command_hierarchy
from q2lsp.qiime.types import CommandHierarchy

__all__ = ["Q2CliGateway", "build_qiime_hierarchy_via_gateway"]


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
