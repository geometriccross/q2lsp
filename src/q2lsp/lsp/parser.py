"""Shell parser for QIIME2 CLI completion.

Handles line continuations, shell tokenization with quote handling,
and QIIME command detection for completion context.
"""

from __future__ import annotations

from q2lsp.lsp.types import ParsedCommand, TokenSpan


def merge_line_continuations(text: str) -> tuple[str, list[int]]:
    """
    Merge lines with backslash continuations into a single line.

    Args:
        text: The input text potentially containing backslash line continuations.

    Returns:
        A tuple of (merged_text, offset_map) where:
        - merged_text: Text with continuations merged (backslash+newline removed)
        - offset_map: Maps merged position -> original position.
                      Length is len(merged_text) + 1 for boundary mapping.
    """
    merged: list[str] = []
    offset_map: list[int] = []
    i = 0
    n = len(text)

    while i < n:
        # Check for backslash followed by newline (line continuation)
        if text[i] == "\\" and i + 1 < n and text[i + 1] == "\n":
            # Skip the backslash and newline - don't add to merged
            i += 2
            continue

        # Regular character - add to merged and record mapping
        offset_map.append(i)
        merged.append(text[i])
        i += 1

    # Add final boundary mapping (position after last char)
    offset_map.append(i)

    return "".join(merged), offset_map


def tokenize_shell_line(line: str, line_start_offset: int) -> list[TokenSpan]:
    """
    Tokenize a shell line respecting quotes.

    Args:
        line: The shell line to tokenize (already merged, no continuations).
        line_start_offset: Offset in original text where this line starts.

    Returns:
        List of TokenSpan with positions relative to original text.

    Quote handling:
        - Single quotes: no escapes inside, everything is literal
        - Double quotes: backslash escapes the next character
        - Unquoted: backslash escapes the next character
    """
    tokens: list[TokenSpan] = []
    i = 0
    n = len(line)

    while i < n:
        # Skip whitespace
        while i < n and line[i] in " \t":
            i += 1
        if i >= n:
            break

        # Start of a token
        token_start = i
        token_chars: list[str] = []

        while i < n:
            char = line[i]

            if char in " \t":
                # End of token (unquoted whitespace)
                break
            elif char == "'":
                # Single quoted string - no escapes
                i += 1  # Skip opening quote
                while i < n and line[i] != "'":
                    token_chars.append(line[i])
                    i += 1
                if i < n:
                    i += 1  # Skip closing quote
            elif char == '"':
                # Double quoted string - backslash escapes
                i += 1  # Skip opening quote
                while i < n and line[i] != '"':
                    if line[i] == "\\" and i + 1 < n:
                        i += 1  # Skip backslash
                        token_chars.append(line[i])
                        i += 1
                    else:
                        token_chars.append(line[i])
                        i += 1
                if i < n:
                    i += 1  # Skip closing quote
            elif char == "\\" and i + 1 < n:
                # Unquoted backslash escape
                i += 1  # Skip backslash
                token_chars.append(line[i])
                i += 1
            else:
                # Regular character
                token_chars.append(char)
                i += 1

        if token_chars or i > token_start:
            tokens.append(
                TokenSpan(
                    text="".join(token_chars),
                    start=line_start_offset + token_start,
                    end=line_start_offset + i,
                )
            )

    return tokens


def find_qiime_commands(text: str) -> list[ParsedCommand]:
    """
    Find all QIIME commands in the text.

    Splits on command separators (;, &&, ||, |, newline) outside quotes,
    then looks for commands starting with "qiime".

    Args:
        text: The full text to parse (already merged).

    Returns:
        List of ParsedCommand for each qiime command found.
    """
    commands: list[ParsedCommand] = []

    # Split into command segments at separators
    segments = _split_commands(text)

    for seg_start, seg_end in segments:
        segment = text[seg_start:seg_end]
        tokens = tokenize_shell_line(segment, seg_start)

        # Check if first token is "qiime"
        if tokens and tokens[0].text == "qiime":
            commands.append(
                ParsedCommand(
                    tokens=tokens,
                    start=tokens[0].start,
                    end=seg_end,
                )
            )

    return commands


def _split_commands(text: str) -> list[tuple[int, int]]:
    """
    Split text into command segments at ;, &&, ||, |, and newline.

    Returns list of (start, end) tuples for each segment.
    """
    segments: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    seg_start = 0
    in_single_quote = False
    in_double_quote = False

    while i < n:
        char = text[i]

        if in_single_quote:
            if char == "'":
                in_single_quote = False
            i += 1
        elif in_double_quote:
            if char == "\\" and i + 1 < n:
                i += 2  # Skip escaped char
            elif char == '"':
                in_double_quote = False
                i += 1
            else:
                i += 1
        else:
            # Check for separators
            if char == "'":
                in_single_quote = True
                i += 1
            elif char == '"':
                in_double_quote = True
                i += 1
            elif char == "\\" and i + 1 < n:
                i += 2  # Skip escaped char
            elif char == ";" or char == "\n":
                # Single char separator
                if i > seg_start:
                    segments.append((seg_start, i))
                seg_start = i + 1
                i += 1
            elif char == "|":
                # Could be | or ||
                if i + 1 < n and text[i + 1] == "|":
                    if i > seg_start:
                        segments.append((seg_start, i))
                    seg_start = i + 2
                    i += 2
                else:
                    if i > seg_start:
                        segments.append((seg_start, i))
                    seg_start = i + 1
                    i += 1
            elif char == "&" and i + 1 < n and text[i + 1] == "&":
                # &&
                if i > seg_start:
                    segments.append((seg_start, i))
                seg_start = i + 2
                i += 2
            else:
                i += 1

    # Add final segment
    if i > seg_start:
        segments.append((seg_start, i))

    return segments


def command_at_position(
    commands: list[ParsedCommand], offset: int
) -> ParsedCommand | None:
    """
    Find the command containing the given offset.

    Args:
        commands: List of parsed QIIME commands.
        offset: Position in the original text.

    Returns:
        The ParsedCommand containing the offset, or None if not in any command.
    """
    for cmd in commands:
        if cmd.start <= offset <= cmd.end:
            return cmd
    return None


# Re-export for backward compatibility
from q2lsp.lsp.completion_context import get_completion_context

__all__ = [
    "merge_line_continuations",
    "tokenize_shell_line",
    "find_qiime_commands",
    "command_at_position",
    "get_completion_context",  # re-exported from completion_context
]
