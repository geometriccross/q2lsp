"""Immutable source snapshot, shell analysis, and coordinate mapping.

Syntax spans use merged-text code-point offsets. Only this module translates
those offsets back to the original source; UTF-16 conversion happens last.
"""

from __future__ import annotations

import re
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field

from q2lsp.core.shell import (
    ParsedCommand,
    TokenSpan,
    command_at_position,
    find_qiime_commands,
    merge_line_continuations,
    tokenize_shell_line,
)


@dataclass(frozen=True)
class OffsetMapper:
    """Index source lines once and map code points to UTF-16 columns."""

    text: str
    _starts: tuple[int, ...] = field(init=False, repr=False)
    _ends: tuple[int, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        breaks = tuple(re.finditer(r"\r\n|\r|\n", self.text))
        object.__setattr__(self, "_starts", (0, *(match.end() for match in breaks)))
        object.__setattr__(
            self, "_ends", (*(match.start() for match in breaks), len(self.text))
        )

    def offset_to_position(self, offset: int) -> tuple[int, int]:
        offset = max(0, min(offset, len(self.text)))
        line = bisect_right(self._starts, offset) - 1
        end = min(offset, self._ends[line])
        return line, sum(
            _utf16_width(char) for char in self.text[self._starts[line] : end]
        )

    def position_to_offset(self, line: int, character: int) -> int:
        line = max(0, line)
        if line >= len(self._starts):
            return len(self.text)
        target = max(0, character)
        units = 0
        for offset in range(self._starts[line], self._ends[line]):
            units += _utf16_width(self.text[offset])
            if units > target:
                return offset
        return self._ends[line]


def _utf16_width(char: str) -> int:
    return 2 if ord(char) > 0xFFFF else 1


@dataclass(frozen=True)
class CursorContext:
    """Shared cursor facts, without completion modes or protocol types."""

    command: ParsedCommand | None = None
    current_token: TokenSpan | None = None
    token_index: int = -1
    prefix: str = ""
    prefix_start: int = 0  # Merged offset; may exclude an opening quote.


@dataclass(frozen=True)
class Document:
    source: str
    merged_text: str
    offset_map: tuple[int, ...]
    commands: tuple[ParsedCommand, ...]
    positions: OffsetMapper

    def original_offset(self, merged_offset: int) -> int:
        if merged_offset < 0:
            raise ValueError("merged_offset must be non-negative")
        if merged_offset >= len(self.offset_map):
            raise ValueError("merged_offset exceeds offset_map size")
        return self.offset_map[merged_offset]

    def merged_offset(self, original_offset: int) -> int:
        if original_offset < 0:
            raise ValueError("original_offset must be non-negative")
        return min(
            bisect_left(self.offset_map, original_offset), len(self.offset_map) - 1
        )

    def original_span(self, start: int, end: int) -> tuple[int, int]:
        """Map a half-open span, excluding a continuation just after its end."""
        original_start = self.original_offset(start)
        original_end = (
            self.original_offset(end - 1) + 1 if end > start else original_start
        )
        return original_start, original_end

    def command_text(self, command: ParsedCommand) -> str:
        return self.source[
            self.original_offset(command.start) : self.original_offset(command.end)
        ]

    def cursor_at(self, original_offset: int) -> CursorContext:
        offset = self.merged_offset(max(0, original_offset))
        command = command_at_position(self.commands, offset)
        # A cursor sits between characters: immediately before a separator is
        # still an editing position in the preceding command.
        if command is None and offset > 0:
            command = command_at_position(self.commands, offset - 1)
        if command is None:
            return CursorContext()

        for index, token in enumerate(command.tokens):
            if offset < token.start:
                return CursorContext(command=command, token_index=index)
            if offset <= token.end:
                raw_prefix = self.merged_text[token.start : offset]
                words = tokenize_shell_line(raw_prefix, token.start)
                prefix = words[0].text if words else ""
                prefix_start = token.start
                if words and words[0].unclosed_quote == raw_prefix[:1]:
                    prefix_start += 1
                return CursorContext(
                    command=command,
                    current_token=token,
                    token_index=index,
                    prefix=prefix,
                    prefix_start=prefix_start,
                )
        return CursorContext(command=command, token_index=len(command.tokens))


def analyze_document(source: str) -> Document:
    merged_text, offset_map = merge_line_continuations(source)
    return Document(
        source=source,
        merged_text=merged_text,
        offset_map=tuple(offset_map),
        commands=tuple(find_qiime_commands(merged_text)),
        positions=OffsetMapper(source),
    )
