"""Standalone textDocument/hover handler behavior."""

from __future__ import annotations

from collections.abc import Callable

from lsprotocol import types
from pygls.workspace import TextDocument

from q2lsp.lsp.adapter import position_to_offset
from q2lsp.lsp.document_commands import analyze_document, resolve_completion_context
from q2lsp.lsp.hover import get_hover_help


def handle_hover(
    document: TextDocument,
    position: types.Position,
    get_help: Callable[[list[str]], str | None],
) -> types.Hover | None:
    """Return hover help for a document position."""
    offset = position_to_offset(document, position)
    doc = analyze_document(document.source)
    ctx = resolve_completion_context(doc, offset)
    help_text = get_hover_help(ctx, get_help=get_help)

    if help_text is None:
        return None

    return types.Hover(
        contents=types.MarkupContent(
            kind=types.MarkupKind.Markdown,
            value=f"```\n{help_text}\n```",
        ),
    )
