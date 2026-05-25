"""Standalone textDocument/completion handler behavior."""

from __future__ import annotations

from lsprotocol import types
from pygls.workspace import TextDocument

from q2lsp.lsp.adapter import position_to_offset, to_lsp_completion_item
from q2lsp.lsp.document_commands import analyze_document, resolve_completion_context
from q2lsp.qiime.catalog import CatalogProvider
from q2lsp.usecases.get_completions_usecase import CompletionRequest, get_completions


def handle_completion(
    document: TextDocument,
    position: types.Position,
    get_catalog: CatalogProvider,
) -> types.CompletionList:
    """Return completion items for a document position."""
    doc = analyze_document(document.source)
    offset = position_to_offset(document, position)
    ctx = resolve_completion_context(doc, offset)

    command_tokens: tuple[str, ...] = ()
    if ctx.command is not None:
        command_tokens = tuple(token.text for token in ctx.command.tokens)
    request = CompletionRequest(
        mode=str(ctx.mode),
        prefix=ctx.prefix,
        command_tokens=command_tokens,
    )
    internal_items = get_completions(request, get_catalog())
    lsp_items = [
        to_lsp_completion_item(item, position=position, prefix=ctx.prefix)
        for item in internal_items
    ]

    return types.CompletionList(is_incomplete=False, items=lsp_items)
