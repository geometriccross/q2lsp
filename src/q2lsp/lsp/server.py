"""QIIME2 LSP Server using pygls 2.0.

Provides completion support for QIIME2 CLI commands in shell scripts.
"""

from __future__ import annotations

import logging

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from q2lsp.logging import get_logger
from q2lsp.lsp.adapter import (
    position_to_offset as _position_to_offset,
    to_lsp_completion_item as _to_lsp_completion_item,
)
from q2lsp.lsp.completions import get_completions
from q2lsp.lsp.error_handling import wrap_handler
from q2lsp.lsp.parser import get_completion_context
from q2lsp.qiime.hierarchy_provider import HierarchyProvider


def create_server(
    *,
    get_hierarchy: HierarchyProvider,
    logger: logging.Logger | None = None,
) -> LanguageServer:
    """
    Create and configure the LSP server.

    Args:
        get_hierarchy: Provider function for QIIME2 command hierarchy.
        logger: Optional logger instance. If None, uses default q2lsp.lsp logger.

    Returns:
        Configured LanguageServer instance with completion support.
    """
    if logger is None:
        logger = get_logger("lsp")

    server = LanguageServer("q2lsp", "v0.1.0")

    def _empty_completion_list() -> types.CompletionList:
        return types.CompletionList(is_incomplete=False, items=[])

    @server.feature(
        types.TEXT_DOCUMENT_COMPLETION,
        types.CompletionOptions(
            trigger_characters=[" ", "-"],
            resolve_provider=False,
        ),
    )
    @wrap_handler(
        logger=logger,
        feature_name="textDocument/completion",
        default_factory=_empty_completion_list,
    )
    def completion(params: types.CompletionParams) -> types.CompletionList:
        """
        Handle textDocument/completion requests.

        Provides completion for QIIME2 CLI commands in shell scripts.
        """
        logger.debug("Completion request at %s", params.position)

        document = server.workspace.get_text_document(params.text_document.uri)

        # Calculate document offset from line/character position
        offset = _position_to_offset(document, params.position)

        # Get completion context from parser
        ctx = get_completion_context(document.source, offset)
        logger.debug("Completion context: mode=%s, prefix=%s", ctx.mode, ctx.prefix)

        # Get completion items
        hierarchy = get_hierarchy()
        internal_items = get_completions(ctx, hierarchy)

        # Convert to LSP CompletionItems
        lsp_items = [_to_lsp_completion_item(item) for item in internal_items]

        logger.debug("Returning %d completion items", len(lsp_items))
        return types.CompletionList(
            is_incomplete=False,
            items=lsp_items,
        )

    return server
