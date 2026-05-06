"""Adapter module for converting between internal types and LSP protocol types."""

from __future__ import annotations

from lsprotocol import types
from pygls.workspace import TextDocument

from q2lsp.core.document import DocumentSnapshot
from q2lsp.core.types import (
    CompletionItem as InternalCompletionItem,
    CompletionKind,
)

__all__ = [
    "LSP_POSITION_ENCODING",
    "completion_kind_to_lsp",
    "offset_to_position",
    "position_to_offset",
    "to_lsp_completion_item",
]

LSP_POSITION_ENCODING = types.PositionEncodingKind.Utf16

_COMPLETION_KIND_TO_LSP: dict[str, types.CompletionItemKind] = {
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
    snapshot = _document_snapshot(document)
    return snapshot.offset_mapper().position_to_offset(position.line, position.character)


def offset_to_position(document: TextDocument, offset: int) -> types.Position:
    """
    Convert document offset to LSP Position (line, character).

    Args:
        document: The text document
        offset: 0-based offset in the document

    Returns:
        LSP Position with 0-based line and character
    """
    snapshot = _document_snapshot(document)
    line, character = snapshot.offset_mapper().offset_to_position(offset)
    return types.Position(line=line, character=character)


def _document_snapshot(document: TextDocument) -> DocumentSnapshot:
    return DocumentSnapshot(uri=document.uri, text=document.source, version=document.version)


def completion_kind_to_lsp(kind: CompletionKind | str) -> types.CompletionItemKind:
    """
    Map internal CompletionKind to LSP CompletionItemKind.

    Args:
        kind: Internal completion kind value

    Returns:
        LSP CompletionItemKind enum value
    """
    return _COMPLETION_KIND_TO_LSP.get(str(kind), types.CompletionItemKind.Text)


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
