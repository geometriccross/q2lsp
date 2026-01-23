"""Cursor marker helper for test fixtures.

Provides utilities to extract cursor position from test strings with markers,
making test fixtures more readable.

Example:
    >>> text, position = extract_cursor(text_with_cursor="qiime <CURSOR>info")
    >>> text
    'qiime info'
    >>> position
    Position(line=0, character=6)
"""

from __future__ import annotations

from lsprotocol.types import Position


def extract_cursor(
    *,
    text_with_cursor: str,
    marker: str = "<CURSOR>",
) -> tuple[str, Position]:
    """
    Extract cursor position from text containing a marker.

    Args:
        text_with_cursor: Text containing exactly one cursor marker.
        marker: The marker string to look for (default: "<CURSOR>").

    Returns:
        Tuple of (cleaned text without marker, Position at marker location).

    Raises:
        ValueError: If marker appears zero or more than one time.
    """
    count = text_with_cursor.count(marker)
    if count == 0:
        raise ValueError(f"Cursor marker '{marker}' not found in text")
    if count > 1:
        raise ValueError(
            f"Multiple cursor markers '{marker}' found in text (expected exactly 1)"
        )

    # Find marker position
    marker_index = text_with_cursor.index(marker)

    # Calculate line and character
    text_before_cursor = text_with_cursor[:marker_index]
    lines_before = text_before_cursor.split("\n")
    line = len(lines_before) - 1
    character = len(lines_before[-1])

    # Remove marker from text
    cleaned_text = text_with_cursor.replace(marker, "", 1)

    return cleaned_text, Position(line=line, character=character)


def extract_cursor_offset(
    *,
    text_with_cursor: str,
    marker: str = "<CURSOR>",
) -> tuple[str, int]:
    """
    Extract cursor offset from text containing a marker.

    This is useful for testing parser functions that work with byte/char offsets.

    Args:
        text_with_cursor: Text containing exactly one cursor marker.
        marker: The marker string to look for (default: "<CURSOR>").

    Returns:
        Tuple of (cleaned text without marker, offset at marker location).

    Raises:
        ValueError: If marker appears zero or more than one time.
    """
    count = text_with_cursor.count(marker)
    if count == 0:
        raise ValueError(f"Cursor marker '{marker}' not found in text")
    if count > 1:
        raise ValueError(
            f"Multiple cursor markers '{marker}' found in text (expected exactly 1)"
        )

    # Find marker position (this is the offset)
    offset = text_with_cursor.index(marker)

    # Remove marker from text
    cleaned_text = text_with_cursor.replace(marker, "", 1)

    return cleaned_text, offset
