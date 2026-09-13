"""The boundary between source coordinates/results and LSP wire types."""

from __future__ import annotations

from lsprotocol import types

from q2lsp.core.document import Document
from q2lsp.core.types import CompletionItem, CompletionKind

LSP_POSITION_ENCODING = types.PositionEncodingKind.Utf16

_COMPLETION_KIND_TO_LSP: dict[str, types.CompletionItemKind] = {
    CompletionKind.PLUGIN: types.CompletionItemKind.Module,
    CompletionKind.ACTION: types.CompletionItemKind.Function,
    CompletionKind.PARAMETER: types.CompletionItemKind.Field,
    CompletionKind.BUILTIN: types.CompletionItemKind.Class,
}


def position_to_offset(document: Document, position: types.Position) -> int:
    return document.positions.position_to_offset(position.line, position.character)


def offset_to_position(document: Document, offset: int) -> types.Position:
    line, character = document.positions.offset_to_position(offset)
    return types.Position(line=line, character=character)


def merged_range(document: Document, start: int, end: int) -> types.Range:
    source_start, source_end = document.original_span(start, end)
    return types.Range(
        start=offset_to_position(document, source_start),
        end=offset_to_position(document, source_end),
    )


def completion_kind_to_lsp(kind: CompletionKind | str) -> types.CompletionItemKind:
    return _COMPLETION_KIND_TO_LSP.get(kind, types.CompletionItemKind.Text)


def to_lsp_completion_item(
    item: CompletionItem,
    edit_range: types.Range | None = None,
    *,
    retained_prefix: str = "",
) -> types.CompletionItem:
    new_text = item.insert_text or item.label
    return types.CompletionItem(
        label=item.label,
        detail=item.detail,
        kind=completion_kind_to_lsp(item.kind),
        insert_text=item.insert_text or None,
        text_edit=types.TextEdit(
            range=edit_range, new_text=new_text[len(retained_prefix) :]
        )
        if edit_range is not None
        else None,
    )
