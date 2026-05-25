"""Unified document analysis for LSP handlers.

Provides a single pipeline: source text -> continuation merging -> command parsing,
with transparent bidirectional offset mapping between original and merged text.
"""

from __future__ import annotations

from bisect import bisect_left
from typing import NamedTuple

from collections.abc import Sequence

from q2lsp.lsp.parser import (
    command_at_position,
    find_qiime_commands,
    merge_line_continuations,
)
from q2lsp.lsp.types import CompletionContext, CompletionMode, ParsedCommand, TokenSpan


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
    if original_offset < 0:
        original_offset = 0
    merged_offset = to_merged_offset(doc, original_offset)
    return _resolve_context_from_merged(doc.merged_text, merged_offset, doc.commands)


def _resolve_context_from_merged(
    merged_text: str,
    merged_offset: int,
    commands: Sequence[ParsedCommand],
) -> CompletionContext:
    command = command_at_position(list(commands), merged_offset)
    if command is None and merged_offset == len(merged_text) and merged_offset > 0:
        command = command_at_position(list(commands), merged_offset - 1)

    if command is None:
        return CompletionContext(
            mode=CompletionMode.NONE,
            command=None,
            current_token=None,
            token_index=-1,
            prefix="",
        )

    current_token: TokenSpan | None = None
    token_index = -1
    prefix = ""

    for i, token in enumerate(command.tokens):
        if token.start <= merged_offset <= token.end:
            current_token = token
            token_index = i
            prefix = token.text[: merged_offset - token.start]
            break
        if token.end < merged_offset:
            token_index = i + 1

    if current_token is None and token_index >= 0:
        if merged_offset > 0 and merged_offset <= len(merged_text):
            if (
                merged_offset == len(merged_text)
                or merged_text[merged_offset - 1] in " \t"
            ):
                token_index = len(command.tokens)

    return CompletionContext(
        mode=_completion_mode_for_token(token_index),
        command=command,
        current_token=current_token,
        token_index=token_index,
        prefix=prefix,
    )


def _completion_mode_for_token(token_index: int) -> CompletionMode:
    if token_index < 0:
        return CompletionMode.NONE
    if token_index == 0:
        return CompletionMode.NONE
    if token_index == 1:
        return CompletionMode.ROOT
    if token_index == 2:
        return CompletionMode.PLUGIN
    return CompletionMode.PARAMETER
