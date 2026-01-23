"""Tests for cursor marker helper."""

from __future__ import annotations

import pytest
from lsprotocol.types import Position

from tests.helpers.cursor import extract_cursor, extract_cursor_offset


class TestExtractCursor:
    """Tests for extract_cursor function."""

    def test_single_line_start(self) -> None:
        """Cursor at start of single line."""
        text, pos = extract_cursor(text_with_cursor="<CURSOR>qiime info")
        assert text == "qiime info"
        assert pos == Position(line=0, character=0)

    def test_single_line_middle(self) -> None:
        """Cursor in middle of single line."""
        text, pos = extract_cursor(text_with_cursor="qiime <CURSOR>info")
        assert text == "qiime info"
        assert pos == Position(line=0, character=6)

    def test_single_line_end(self) -> None:
        """Cursor at end of single line."""
        text, pos = extract_cursor(text_with_cursor="qiime info<CURSOR>")
        assert text == "qiime info"
        assert pos == Position(line=0, character=10)

    def test_multiline_first_line(self) -> None:
        """Cursor on first line of multiline text."""
        text, pos = extract_cursor(text_with_cursor="line1 <CURSOR>text\nline2")
        assert text == "line1 text\nline2"
        assert pos == Position(line=0, character=6)

    def test_multiline_second_line(self) -> None:
        """Cursor on second line of multiline text."""
        text, pos = extract_cursor(text_with_cursor="line1\nline2 <CURSOR>text")
        assert text == "line1\nline2 text"
        assert pos == Position(line=1, character=6)

    def test_multiline_at_line_start(self) -> None:
        """Cursor at start of a line."""
        text, pos = extract_cursor(text_with_cursor="line1\n<CURSOR>line2")
        assert text == "line1\nline2"
        assert pos == Position(line=1, character=0)

    def test_custom_marker(self) -> None:
        """Can use custom marker."""
        text, pos = extract_cursor(text_with_cursor="qiime |info", marker="|")
        assert text == "qiime info"
        assert pos == Position(line=0, character=6)

    def test_missing_marker_raises(self) -> None:
        """Raises ValueError when marker is missing."""
        with pytest.raises(ValueError, match="not found"):
            extract_cursor(text_with_cursor="qiime info")

    def test_multiple_markers_raises(self) -> None:
        """Raises ValueError when multiple markers present."""
        with pytest.raises(ValueError, match="Multiple"):
            extract_cursor(text_with_cursor="<CURSOR>qiime <CURSOR>info")


class TestExtractCursorOffset:
    """Tests for extract_cursor_offset function."""

    def test_offset_at_start(self) -> None:
        """Offset 0 at start."""
        text, offset = extract_cursor_offset(text_with_cursor="<CURSOR>qiime")
        assert text == "qiime"
        assert offset == 0

    def test_offset_in_middle(self) -> None:
        """Offset in middle of text."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime <CURSOR>info")
        assert text == "qiime info"
        assert offset == 6

    def test_offset_at_end(self) -> None:
        """Offset at end of text."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime<CURSOR>")
        assert text == "qiime"
        assert offset == 5

    def test_multiline_offset(self) -> None:
        """Offset counts newlines."""
        text, offset = extract_cursor_offset(text_with_cursor="ab\ncd<CURSOR>ef")
        assert text == "ab\ncdef"
        assert offset == 5  # 'ab\ncd' = 5 characters

    def test_missing_marker_raises(self) -> None:
        """Raises ValueError when marker is missing."""
        with pytest.raises(ValueError, match="not found"):
            extract_cursor_offset(text_with_cursor="qiime info")

    def test_multiple_markers_raises(self) -> None:
        """Raises ValueError when multiple markers present."""
        with pytest.raises(ValueError, match="Multiple"):
            extract_cursor_offset(text_with_cursor="<CURSOR>q<CURSOR>")
