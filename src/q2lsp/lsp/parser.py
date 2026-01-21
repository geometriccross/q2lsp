"""Parser for QIIME 2 shell command completion."""

from __future__ import annotations

from q2lsp.lsp.types import ParseContext, Token


def collect_continued_lines(
    lines: list[str],
    line_index: int,
) -> tuple[str, int]:
    """
    Join lines with backslash line continuations.

    Args:
        lines: List of complete lines from the document.
        line_index: The line index where the cursor is located.

    Returns:
        A tuple of (joined_line, start_line_index) where joined_line contains
        all continued lines merged into one with single spaces, and
        start_line_index is the index of the first line in the continuation.
    """
    # Find the start of the continued line block
    start_index = line_index

    # Walk backwards to find the start of the continuation block
    while start_index > 0:
        previous_line = lines[start_index - 1].rstrip()
        if previous_line.endswith("\\"):
            start_index -= 1
        else:
            break

    # Collect all lines from start to current
    continued_lines = []
    for i in range(start_index, line_index + 1):
        line = lines[i].rstrip()
        # Remove trailing backslash if present
        if line.endswith("\\"):
            line = line[:-1]
        continued_lines.append(line)

    # Join with single spaces
    joined_line = " ".join(line.rstrip() for line in continued_lines)

    return joined_line, start_index


def tokenize_shell(line: str) -> list[Token]:
    """
    Basic shell tokenization respecting quotes and backslash escapes.

    Args:
        line: The shell command line to tokenize.

    Returns:
        A list of Token objects, each with text, start offset, and end offset.
    """
    tokens: list[Token] = []
    i = 0
    n = len(line)

    while i < n:
        # Skip whitespace
        while i < n and line[i].isspace():
            i += 1
        if i >= n:
            break

        # Record start position
        start = i
        text_parts: list[str] = []
        state: Literal["normal", "single_quote", "double_quote"] = "normal"

        while i < n:
            char = line[i]

            if state == "normal":
                if char.isspace():
                    # End of token
                    break
                elif char == "\\" and i + 1 < n:
                    # Escape sequence
                    text_parts.append(line[i + 1])
                    i += 2
                    continue
                elif char == "'":
                    state = "single_quote"
                elif char == '"':
                    state = "double_quote"
                else:
                    text_parts.append(char)
                i += 1
            elif state == "single_quote":
                if char == "'":
                    state = "normal"
                else:
                    text_parts.append(char)
                i += 1
            elif state == "double_quote":
                if char == "\\" and i + 1 < n:
                    # Escape sequence in double quotes
                    text_parts.append(line[i + 1])
                    i += 2
                    continue
                elif char == '"':
                    state = "normal"
                else:
                    text_parts.append(char)
                i += 1

        if text_parts:
            tokens.append(
                Token(
                    text="".join(text_parts),
                    start=start,
                    end=i,  # i is at the position after the last character
                )
            )

    return tokens


def find_qiime_command_start(tokens: list[Token]) -> int | None:
    """
    Find the index of the most recent 'qiime' command.

    Scans tokens treating ;, |, && as command boundaries.
    Returns the index of the 'qiime' token after the last boundary.

    Args:
        tokens: List of tokens from tokenize_shell.

    Returns:
        Index of the 'qiime' token, or None if not found.
    """
    qiime_index: int | None = None
    boundary_indices: list[int] = []

    for i, token in enumerate(tokens):
        if token.text in (";", "|", "&&"):
            boundary_indices.append(i)
        elif token.text == "qiime":
            qiime_index = i

    if qiime_index is None:
        return None

    # Find the last boundary before the qiime token
    last_boundary = -1
    for boundary in boundary_indices:
        if boundary < qiime_index:
            last_boundary = boundary

    # Check if qiime is after the last boundary
    if qiime_index > last_boundary:
        return qiime_index

    return None


def parse_context(
    lines: list[str],
    line: int,
    character: int,
) -> ParseContext:
    """
    Parse the context around the cursor for completion.

    Args:
        lines: List of complete lines from the document.
        line: The line number where the cursor is located.
        character: The character offset within the line.

    Returns:
        A ParseContext containing tokens, current token info, and cursor offset.
    """
    # Get the full command line with continuations
    full_line, start_line_index = collect_continued_lines(lines, line)

    # Calculate the cursor offset within the full line
    cursor_offset = character
    for i in range(start_line_index, line):
        cursor_offset += len(lines[i].rstrip())
        if i < line:
            cursor_offset += 1  # Account for space continuation

    # Tokenize the full line
    tokens = tokenize_shell(full_line)

    # Find the current token containing the cursor
    current_token_index: int | None = None
    for i, token in enumerate(tokens):
        if token.start <= cursor_offset <= token.end:
            current_token_index = i
            break

    return ParseContext(
        tokens=tokens,
        current_token_index=current_token_index,
        cursor_offset=cursor_offset,
    )
