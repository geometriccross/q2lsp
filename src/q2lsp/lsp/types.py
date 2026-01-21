"""Type definitions for LSP completion."""

from __future__ import annotations

from typing import Literal, TypedDict, TypeAlias


# Cursor Position: (line, column) zero-based
CursorPosition: TypeAlias = tuple[int, int]


# Token Types
class Token(TypedDict):
    """Represents a parsed token from command line input."""

    text: str
    start: int
    end: int
    type: Literal["command", "option", "argument", "unknown"]


# Parse Context
class ParseContext(TypedDict):
    """Context information about the parsed command line."""

    line: str
    tokens: list[Token]
    cursor_pos: CursorPosition


# Command Context
class CommandContext(TypedDict):
    """Context information about the command being completed."""

    plugin: str | None
    action: str | None
    option: str | None
    remaining_args: list[str]


# Completion Mode
CompletionMode: TypeAlias = Literal["command", "plugin", "action", "option", "argument"]
