"""Type definitions for LSP shell parser."""

from __future__ import annotations

from typing import NamedTuple

from q2lsp.core.types import CompletionMode
from q2lsp.qiime.options import OptionGroup, group_option_tokens


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

    @property
    def options(self) -> tuple[OptionGroup[TokenSpan], ...]:
        return group_option_tokens(self.tokens, lambda token: token.text, start_index=3)


class CompletionContext(NamedTuple):
    """Context for completion at a specific position."""

    mode: CompletionMode
    command: ParsedCommand | None  # The QIIME command containing the cursor
    current_token: TokenSpan | None  # Token at cursor (may be partial)
    token_index: int  # Index of current token in command (0-based)
    prefix: str  # Text before cursor in current token
