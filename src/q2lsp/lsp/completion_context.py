"""Completion context determination for QIIME2 CLI commands.

Builds CompletionContext from parsed shell commands to determine
what type of completion is needed at a given cursor position.
"""

from __future__ import annotations

from q2lsp.lsp.parser import (
    command_at_position,
    find_qiime_commands,
    merge_line_continuations,
)
from q2lsp.lsp.types import CompletionContext, CompletionMode, TokenSpan


def get_completion_context(text: str, offset: int) -> CompletionContext:
    """
    Get completion context at the given position.

    This is the main entry point for determining completion context.

    Args:
        text: The full document text.
        offset: Cursor position (0-based offset in original text).

    Returns:
        CompletionContext with mode, command, current token, etc.
    """
    # Merge line continuations
    merged_text, offset_map = merge_line_continuations(text)

    # Convert offset to merged position
    merged_offset = _original_to_merged_offset(offset, offset_map)

    # Find all qiime commands
    commands = find_qiime_commands(merged_text)

    # Find command at cursor position
    command = command_at_position(commands, merged_offset)

    if command is None:
        return CompletionContext(
            mode=CompletionMode.NONE,
            command=None,
            current_token=None,
            token_index=-1,
            prefix="",
        )

    # Find current token and its index
    current_token: TokenSpan | None = None
    token_index = -1
    prefix = ""

    for i, token in enumerate(command.tokens):
        if token.start <= merged_offset <= token.end:
            current_token = token
            token_index = i
            prefix = token.text[: merged_offset - token.start]
            break
        elif token.end < merged_offset:
            token_index = i + 1

    # If cursor is between tokens or after last token
    if current_token is None and token_index >= 0:
        if merged_offset > 0 and merged_offset <= len(merged_text):
            if (
                merged_offset == len(merged_text)
                or merged_text[merged_offset - 1] in " \t"
            ):
                token_index = len(command.tokens)

    # Determine completion mode based on token index
    mode = _determine_mode(token_index)

    return CompletionContext(
        mode=mode,
        command=command,
        current_token=current_token,
        token_index=token_index,
        prefix=prefix,
    )


def _original_to_merged_offset(original_offset: int, offset_map: list[int]) -> int:
    """Convert original text offset to merged text offset."""
    for merged_idx, orig_idx in enumerate(offset_map):
        if orig_idx >= original_offset:
            return merged_idx
    return len(offset_map) - 1


def _determine_mode(token_index: int) -> CompletionMode:
    """
    Determine completion mode based on token position.

    Token 0: "qiime" command itself - no completion needed here
    Token 1: plugin name -> "root" mode (completing plugin/builtin)
    Token 2: action name -> "plugin" mode (completing action within plugin)
    Token >= 3: parameters -> "parameter" mode
    """
    if token_index < 0:
        return CompletionMode.NONE
    elif token_index == 0:
        return CompletionMode.NONE
    elif token_index == 1:
        return CompletionMode.ROOT
    elif token_index == 2:
        return CompletionMode.PLUGIN
    else:
        return CompletionMode.PARAMETER
