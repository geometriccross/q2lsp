"""Resolve the command path whose CLI help should be shown on hover."""

from __future__ import annotations

from collections.abc import Callable

from q2lsp.lsp.types import CompletionContext


def get_hover_help(
    context: CompletionContext,
    *,
    get_help: Callable[[list[str]], str | None],
) -> str | None:
    if context.command is None or context.current_token is None:
        return None
    if not 0 <= context.token_index <= 2:
        return None

    command_path = [
        token.text for token in context.command.tokens[1 : context.token_index + 1]
    ]
    return get_help(command_path)
