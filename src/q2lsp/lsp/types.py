"""Type definitions for LSP shell parser."""

from __future__ import annotations

from enum import Enum

from typing import NamedTuple


class _StrEnum(str, Enum):
    """String-valued enum that behaves like str at runtime."""

    def __str__(self) -> str:
        return str(self.value)


class CompletionMode(_StrEnum):
    """Mode determines what kind of completions to offer."""

    ROOT = "root"
    PLUGIN = "plugin"
    PARAMETER = "parameter"
    NONE = "none"


class CompletionKind(_StrEnum):
    """Kind categorizes completion items."""

    PLUGIN = "plugin"
    ACTION = "action"
    PARAMETER = "parameter"
    BUILTIN = "builtin"


class TokenSpan(NamedTuple):
    """A token with its position in the original text."""

    text: str
    start: int  # Start offset in original text
    end: int  # End offset in original text (exclusive)


class ParsedCommand(NamedTuple):
    """A parsed QIIME command with its tokens and position."""

    tokens: list[TokenSpan]
    start: int  # Start offset in original text
    end: int  # End offset in original text (exclusive)


class CompletionContext(NamedTuple):
    """Context for completion at a specific position."""

    mode: CompletionMode
    command: ParsedCommand | None  # The QIIME command containing the cursor
    current_token: TokenSpan | None  # Token at cursor (may be partial)
    token_index: int  # Index of current token in command (0-based)
    prefix: str  # Text before cursor in current token
