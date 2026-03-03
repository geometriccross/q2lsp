"""Unified document analysis for LSP handlers.

Provides a single pipeline: source text -> continuation merging -> command parsing,
with transparent bidirectional offset mapping between original and merged text.
"""

from __future__ import annotations

from bisect import bisect_left
from typing import NamedTuple

from q2lsp.lsp.completion_context import get_context_from_merged
from q2lsp.lsp.parser import find_qiime_commands, merge_line_continuations
from q2lsp.lsp.types import CompletionContext, ParsedCommand


class AnalyzedDocument(NamedTuple):
    """Result of analyzing a document's QIIME commands.

    Attributes:
        merged_text: Source text with line continuations merged.
        offset_map: Maps each merged-text position to its original-text position.
        commands: All QIIME commands found in the merged text.
    """

    merged_text: str
    offset_map: tuple[int, ...]
    commands: tuple[ParsedCommand, ...]


def analyze_document(source: str) -> AnalyzedDocument:
    """Merge line continuations and parse all QIIME commands.

    Call this once per document snapshot. Pass the result to
    resolve_completion_context, to_original_offset, etc.
    """
    merged_text, offset_map = merge_line_continuations(source)
    commands = find_qiime_commands(merged_text)
    return AnalyzedDocument(
        merged_text=merged_text,
        offset_map=tuple(offset_map),
        commands=tuple(commands),
    )


def to_original_offset(doc: AnalyzedDocument, merged_offset: int) -> int:
    """Map a merged-text offset back to the original source offset.

    Raises ValueError for out-of-range offsets.
    """
    if merged_offset < 0:
        raise ValueError("merged_offset must be non-negative")
    if merged_offset >= len(doc.offset_map):
        raise ValueError("merged_offset exceeds offset_map size")
    return doc.offset_map[merged_offset]


def to_merged_offset(doc: AnalyzedDocument, original_offset: int) -> int:
    """Map an original source offset to the merged-text offset."""
    if original_offset < 0:
        raise ValueError("original_offset must be non-negative")
    merged_offset = bisect_left(doc.offset_map, original_offset)
    if merged_offset >= len(doc.offset_map):
        return len(doc.offset_map) - 1
    return merged_offset


def resolve_completion_context(
    doc: AnalyzedDocument, original_offset: int
) -> CompletionContext:
    """Get completion context at an original-source position."""
    merged_offset = to_merged_offset(doc, original_offset)
    return get_context_from_merged(doc.merged_text, merged_offset, doc.commands)
