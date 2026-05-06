"""Tests for unified document analysis pipeline."""

from __future__ import annotations

import pytest

from tests.helpers.cursor import extract_cursor_offset

from q2lsp.lsp.document_commands import (
    AnalyzedDocument,
    analyze_document,
    resolve_completion_context,
    to_merged_offset,
    to_original_offset,
)
from q2lsp.lsp.types import CompletionMode


class TestAnalyzeDocument:
    """Tests for document analysis pipeline."""

    def test_simple_qiime_command(self) -> None:
        """Analyzing a simple qiime command returns correct structure."""
        doc = analyze_document("qiime info")
        assert isinstance(doc, AnalyzedDocument)
        assert doc.merged_text == "qiime info"
        assert len(doc.commands) == 1
        assert doc.commands[0].tokens[0].text == "qiime"

    def test_with_line_continuation(self) -> None:
        """Line continuations are merged in the analyzed document."""
        doc = analyze_document("qiime \\\ninfo")
        assert doc.merged_text == "qiime info"
        assert len(doc.commands) == 1

    def test_multiple_commands(self) -> None:
        """Multiple qiime commands are all found."""
        doc = analyze_document("qiime info; qiime tools")
        assert len(doc.commands) == 2

    def test_multiple_commands_include_full_spans_and_tokens(self) -> None:
        """Multi-command analysis preserves each command span and token text."""
        doc = analyze_document("echo hi; qiime info --help; qiime tools import")

        assert [(cmd.start, cmd.end) for cmd in doc.commands] == [(9, 26), (28, 46)]
        assert [[token.text for token in cmd.tokens] for cmd in doc.commands] == [
            ["qiime", "info", "--help"],
            ["qiime", "tools", "import"],
        ]

    def test_no_qiime_commands(self) -> None:
        """Non-qiime text returns empty commands."""
        doc = analyze_document("echo hello")
        assert len(doc.commands) == 0

    def test_empty_text(self) -> None:
        """Empty text returns empty analysis."""
        doc = analyze_document("")
        assert doc.merged_text == ""
        assert len(doc.commands) == 0

    def test_offset_map_length(self) -> None:
        """Offset map has correct length (merged_text length + 1)."""
        doc = analyze_document("qiime \\\ninfo")
        assert len(doc.offset_map) == len(doc.merged_text) + 1

    def test_continuation_command_includes_full_span_and_tokens(self) -> None:
        """Continuation analysis exposes full merged command span and tokens."""
        doc = analyze_document("qiime\\\n info --help")

        assert doc.merged_text == "qiime info --help"
        assert len(doc.commands) == 1
        command = doc.commands[0]
        assert (command.start, command.end) == (0, 17)
        assert [(token.text, token.start, token.end) for token in command.tokens] == [
            ("qiime", 0, 5),
            ("info", 6, 10),
            ("--help", 11, 17),
        ]

    def test_commands_is_tuple(self) -> None:
        """Commands should be a tuple (immutable)."""
        doc = analyze_document("qiime info")
        assert isinstance(doc.commands, tuple)

    def test_offset_map_is_tuple(self) -> None:
        """Offset map should be a tuple (immutable)."""
        doc = analyze_document("qiime info")
        assert isinstance(doc.offset_map, tuple)


class TestToOriginalOffset:
    """Tests for merged-to-original offset conversion."""

    def test_no_continuation(self) -> None:
        """Without continuations, offsets are identity."""
        doc = analyze_document("qiime info")
        assert to_original_offset(doc, 0) == 0
        assert to_original_offset(doc, 5) == 5

    def test_after_continuation(self) -> None:
        """Offsets after continuation map to correct original position."""
        # "qiime \\\ninfo" (length 12)
        # merged: "qiime info" (length 10)
        # The 'i' in "info" is at original offset 8, merged offset 6
        doc = analyze_document("qiime \\\ninfo")
        assert to_original_offset(doc, 6) == 8  # 'i' in info

    @pytest.mark.parametrize(
        ("merged_offset", "original_offset"),
        [
            (5, 7),  # space immediately after the continuation
            (10, 12),  # EOF after continuation
        ],
    )
    def test_to_original_offset_around_continuation(
        self, merged_offset: int, original_offset: int
    ) -> None:
        """Merged offsets around a continuation map to independent originals."""
        doc = analyze_document("qiime\\\n info")

        assert to_original_offset(doc, merged_offset) == original_offset

    def test_to_original_offset_with_multiple_continuations(self) -> None:
        """Merged offsets after multiple continuations map to original positions."""
        doc = analyze_document("qiime\\\n tools\\\n import")

        assert doc.merged_text == "qiime tools import"
        assert to_original_offset(doc, 6) == 8  # 't' in tools
        assert to_original_offset(doc, 12) == 16  # 'i' in import
        assert to_original_offset(doc, len(doc.merged_text)) == 22

    def test_negative_offset_raises(self) -> None:
        """Negative merged offset should raise ValueError."""
        doc = analyze_document("qiime info")
        with pytest.raises(ValueError, match="non-negative"):
            to_original_offset(doc, -1)

    def test_overflow_offset_raises(self) -> None:
        """Merged offset beyond map size should raise ValueError."""
        doc = analyze_document("qiime info")
        with pytest.raises(ValueError, match="exceeds"):
            to_original_offset(doc, 9999)


class TestToMergedOffset:
    """Tests for original-to-merged offset conversion."""

    def test_no_continuation(self) -> None:
        """Without continuations, offsets are identity."""
        doc = analyze_document("qiime info")
        assert to_merged_offset(doc, 0) == 0
        assert to_merged_offset(doc, 5) == 5

    def test_after_continuation(self) -> None:
        """Offsets after continuation map to correct merged position."""
        # "qiime \\\ninfo" -> merged "qiime info"
        # Original offset 8 ('i' in info) -> merged offset 6
        doc = analyze_document("qiime \\\ninfo")
        assert to_merged_offset(doc, 8) == 6

    def test_offset_in_continuation_gap(self) -> None:
        """Offset on the backslash itself maps sensibly."""
        # Original offset 6 is the backslash, offset 7 is the newline
        # Both are removed in merged text. Should map to merged offset 6
        doc = analyze_document("qiime \\\ninfo")
        assert to_merged_offset(doc, 6) == 6
        assert to_merged_offset(doc, 7) == 6

    @pytest.mark.parametrize(
        ("text_with_cursor", "merged_offset"),
        [
            ("qiime<CURSOR>\\\n info", 5),  # before/on backslash boundary
            ("qiime\\<CURSOR>\n info", 5),  # on newline boundary
            ("qiime\\\n<CURSOR> info", 5),  # immediately after continuation
        ],
    )
    def test_to_merged_offset_around_continuation(
        self, text_with_cursor: str, merged_offset: int
    ) -> None:
        """Cursor offsets around continuation syntax map to the same boundary."""
        text, offset = extract_cursor_offset(text_with_cursor=text_with_cursor)
        doc = analyze_document(text)

        assert to_merged_offset(doc, offset) == merged_offset

    def test_to_merged_offset_at_eof_after_continuation(self) -> None:
        """EOF after a continuation maps to merged EOF."""
        text = "qiime\\\n info"
        doc = analyze_document(text)

        assert to_merged_offset(doc, len(text)) == len(doc.merged_text)

    def test_to_merged_offset_with_multiple_continuations(self) -> None:
        """Original offsets across multiple continuations map independently."""
        doc = analyze_document("qiime\\\n tools\\\n import")

        assert to_merged_offset(doc, 8) == 6  # 't' in tools
        assert to_merged_offset(doc, 13) == 11  # second backslash
        assert to_merged_offset(doc, 14) == 11  # second newline
        assert to_merged_offset(doc, 15) == 11  # space after second continuation
        assert to_merged_offset(doc, 16) == 12  # 'i' in import

    def test_negative_offset_raises(self) -> None:
        """Negative original offset should raise ValueError."""
        doc = analyze_document("qiime info")
        with pytest.raises(ValueError, match="non-negative"):
            to_merged_offset(doc, -1)

    def test_at_eof(self) -> None:
        """Offset at EOF should map correctly."""
        text = "qiime info"
        doc = analyze_document(text)
        merged = to_merged_offset(doc, len(text))
        assert merged == len(doc.merged_text)


class TestResolveCompletionContext:
    """Tests for getting completion context from analyzed document."""

    def test_plugin_position(self) -> None:
        """Context at plugin position returns ROOT mode."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime <CURSOR>")
        doc = analyze_document(text)
        ctx = resolve_completion_context(doc, offset)
        assert ctx.mode == CompletionMode.ROOT

    def test_action_position(self) -> None:
        """Context at action position returns PLUGIN mode."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime info <CURSOR>")
        doc = analyze_document(text)
        ctx = resolve_completion_context(doc, offset)
        assert ctx.mode == CompletionMode.PLUGIN

    def test_parameter_position(self) -> None:
        """Context at parameter position returns PARAMETER mode."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime info action <CURSOR>"
        )
        doc = analyze_document(text)
        ctx = resolve_completion_context(doc, offset)
        assert ctx.mode == CompletionMode.PARAMETER

    def test_with_line_continuation(self) -> None:
        """Context works correctly with line continuations."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime \\\ninfo <CURSOR>")
        doc = analyze_document(text)
        ctx = resolve_completion_context(doc, offset)
        assert ctx.mode == CompletionMode.PLUGIN

    def test_outside_qiime_command(self) -> None:
        """Context outside qiime command returns NONE."""
        text, offset = extract_cursor_offset(text_with_cursor="echo <CURSOR>hello")
        doc = analyze_document(text)
        ctx = resolve_completion_context(doc, offset)
        assert ctx.mode == CompletionMode.NONE

    def test_partial_prefix(self) -> None:
        """Context with partial token returns correct prefix."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime inf<CURSOR>")
        doc = analyze_document(text)
        ctx = resolve_completion_context(doc, offset)
        assert ctx.mode == CompletionMode.ROOT
        assert ctx.prefix == "inf"

    def test_at_eof(self) -> None:
        """Context at EOF returns sensible result."""
        text = "qiime info "
        doc = analyze_document(text)
        ctx = resolve_completion_context(doc, len(text))
        assert ctx.mode == CompletionMode.PLUGIN

    def test_matches_get_completion_context(self) -> None:
        """resolve_completion_context should match get_completion_context."""
        from q2lsp.lsp.completion_context import get_completion_context

        text = "qiime \\\ninfo action --help"
        for offset in range(len(text) + 1):
            doc = analyze_document(text)
            ctx_new = resolve_completion_context(doc, offset)
            ctx_old = get_completion_context(text, offset)
            assert ctx_new.mode == ctx_old.mode, f"Mode mismatch at offset {offset}"
            assert ctx_new.prefix == ctx_old.prefix, (
                f"Prefix mismatch at offset {offset}"
            )
            assert ctx_new.token_index == ctx_old.token_index, (
                f"token_index mismatch at offset {offset}"
            )
