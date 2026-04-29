from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentSnapshot:
    """Immutable text snapshot independent of any LSP transport object."""

    uri: str
    text: str
    version: int | None = None

    def offset_mapper(self) -> "OffsetMapper":
        return OffsetMapper(self.text)


@dataclass(frozen=True)
class OffsetMapper:
    """Map between Python string offsets and LSP UTF-16 positions."""

    text: str

    def offset_to_position(self, offset: int) -> tuple[int, int]:
        safe_offset = max(0, min(offset, len(self.text)))
        line = 0
        character = 0
        current_offset = 0
        while current_offset < safe_offset:
            char = self.text[current_offset]
            next_offset = current_offset + 1
            if char == "\r" and next_offset < len(self.text) and self.text[next_offset] == "\n":
                if safe_offset <= next_offset:
                    return line, character
                line += 1
                character = 0
                current_offset += 2
            elif char == "\r" or char == "\n":
                line += 1
                character = 0
                current_offset = next_offset
            else:
                character += _utf16_length(char)
                current_offset = next_offset
        return line, character

    def position_to_offset(self, line: int, character: int) -> int:
        line_start, line_end = _line_bounds(self.text, max(0, line))

        target_units = max(0, character)
        units = 0
        for offset in range(line_start, line_end):
            next_units = units + _utf16_length(self.text[offset])
            if next_units > target_units:
                return offset
            units = next_units
        return line_end


def _utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _line_bounds(text: str, target_line: int) -> tuple[int, int]:
    line = 0
    line_start = 0
    current_offset = 0
    while current_offset < len(text):
        char = text[current_offset]
        if char == "\r" and current_offset + 1 < len(text) and text[current_offset + 1] == "\n":
            if line == target_line:
                return line_start, current_offset
            line += 1
            current_offset += 2
            line_start = current_offset
        elif char == "\r" or char == "\n":
            if line == target_line:
                return line_start, current_offset
            line += 1
            current_offset += 1
            line_start = current_offset
        else:
            current_offset += 1

    if line == target_line:
        return line_start, len(text)
    return len(text), len(text)
