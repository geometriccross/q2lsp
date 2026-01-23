"""QIIME2 LSP Server using pygls 2.0.

Provides completion support for QIIME2 CLI commands in shell scripts.
"""

from __future__ import annotations

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from q2lsp.lsp.adapter import (
    position_to_offset as _position_to_offset,
    to_lsp_completion_item as _to_lsp_completion_item,
)
from q2lsp.lsp.completions import get_completions
from q2lsp.lsp.parser import get_completion_context
from q2lsp.qiime.hierarchy_provider import HierarchyProvider


def create_server(*, get_hierarchy: HierarchyProvider) -> LanguageServer:
    """
    Create and configure the LSP server.

    Returns:
        Configured LanguageServer instance with completion support.
    """
    server = LanguageServer("q2lsp", "v0.1.0")

    @server.feature(
        types.TEXT_DOCUMENT_COMPLETION,
        types.CompletionOptions(
            trigger_characters=[" ", "-"],
            resolve_provider=False,
        ),
    )
    def completion(params: types.CompletionParams) -> types.CompletionList:
        """
        Handle textDocument/completion requests.

        Provides completion for QIIME2 CLI commands in shell scripts.
        """
        document = server.workspace.get_text_document(params.text_document.uri)

        # Calculate document offset from line/character position
        offset = _position_to_offset(document, params.position)

        # Get completion context from parser
        ctx = get_completion_context(document.source, offset)

        # Get completion items
        hierarchy = get_hierarchy()
        internal_items = get_completions(ctx, hierarchy)

        # Convert to LSP CompletionItems
        lsp_items = [_to_lsp_completion_item(item) for item in internal_items]

        return types.CompletionList(
            is_incomplete=False,
            items=lsp_items,
        )

    return server
