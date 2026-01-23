"""Shell parser for QIIME2 CLI completion.

Handles line continuations, shell tokenization with quote handling,
and QIIME command detection for completion context.
"""

from __future__ import annotations

from q2lsp.lsp.types import CompletionContext, CompletionMode, ParsedCommand, TokenSpan


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


def get_completion_context(text: str, offset: int) -> CompletionContext:
    """
    Get completion context at the given position.

    This is the main entry point for the parser.

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
            mode="none",
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
            # Prefix is text before cursor within token
            prefix = token.text[: merged_offset - token.start]
            break
        elif token.end < merged_offset:
            # Cursor is after this token - might be starting a new token
            token_index = i + 1

    # If cursor is between tokens or after last token, we're at a new token position
    if current_token is None and token_index >= 0:
        # Check if we're right after a space (new token position)
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
    """
    Convert original text offset to merged text offset.

    The offset_map maps merged_idx -> original_idx.
    We need the reverse: find merged_idx where offset_map[merged_idx] >= original_offset.
    """
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
        return "none"
    elif token_index == 0:
        # On the "qiime" token itself
        return "none"
    elif token_index == 1:
        return "root"
    elif token_index == 2:
        return "plugin"
    else:
        return "parameter"
