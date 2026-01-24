"""Adapter module for converting between internal types and LSP protocol types."""

from __future__ import annotations

from lsprotocol import types
from pygls.workspace import TextDocument

from q2lsp.lsp.completions import CompletionItem as InternalCompletionItem
from q2lsp.lsp.types import CompletionKind

__all__ = [
    "completion_kind_to_lsp",
    "position_to_offset",
    "to_lsp_completion_item",
]

_COMPLETION_KIND_TO_LSP: dict[CompletionKind, types.CompletionItemKind] = {
    CompletionKind.PLUGIN: types.CompletionItemKind.Module,
    CompletionKind.ACTION: types.CompletionItemKind.Function,
    CompletionKind.PARAMETER: types.CompletionItemKind.Field,
    CompletionKind.BUILTIN: types.CompletionItemKind.Class,
}


def position_to_offset(document: TextDocument, position: types.Position) -> int:
    """
    Convert LSP Position (line, character) to document offset.

    Args:
        document: The text document
        position: LSP position with 0-based line and character

    Returns:
        0-based offset in the document
    """
    lines = document.lines
    offset = 0

    for i in range(min(position.line, len(lines))):
        offset += len(lines[i])

    if position.line < len(lines):
        offset += min(position.character, len(lines[position.line]))

    return offset


def completion_kind_to_lsp(kind: CompletionKind) -> types.CompletionItemKind:
    """
    Map internal CompletionKind to LSP CompletionItemKind.

    Args:
        kind: Internal completion kind enum

    Returns:
        LSP CompletionItemKind enum value
    """
    return _COMPLETION_KIND_TO_LSP.get(kind, types.CompletionItemKind.Text)


def to_lsp_completion_item(
    item: InternalCompletionItem,
    position: types.Position | None = None,
    prefix: str = "",
) -> types.CompletionItem:
    """
    Convert internal CompletionItem to LSP CompletionItem.

    Args:
        item: Internal completion item
        position: LSP position where completion is requested (optional)
        prefix: Text prefix to be replaced by text_edit (optional)

    Returns:
        LSP-compatible CompletionItem
    """
    completion_item = types.CompletionItem(
        label=item.label,
        detail=item.detail,
        kind=completion_kind_to_lsp(item.kind),
        insert_text=item.insert_text if item.insert_text else None,
    )

    # If position and prefix are provided, add text_edit to replace the prefix
    if position is not None and prefix:
        start_character = max(0, position.character - len(prefix))
        new_text = item.insert_text if item.insert_text else item.label
        completion_item.text_edit = types.TextEdit(
            range=types.Range(
                start=types.Position(line=position.line, character=start_character),
                end=types.Position(line=position.line, character=position.character),
            ),
            new_text=new_text,
        )

    return completion_item
