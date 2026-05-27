"""Tests for unified document analysis pipeline."""

from __future__ import annotations

import pytest

from tests.helpers.cursor import extract_cursor_offset
from tests.helpers.completions import get_completion_context

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

    def test_resolves_context_across_continuation_offsets(self) -> None:
        """Completion context resolution handles original offsets around continuations."""
        text = "qiime \\\ninfo action --help"
        doc = analyze_document(text)

        expectations = {
            0: CompletionMode.NONE,
            6: CompletionMode.ROOT,
            8: CompletionMode.ROOT,
            len(text): CompletionMode.PARAMETER,
        }
        for offset, mode in expectations.items():
            ctx = resolve_completion_context(doc, offset)
            assert ctx.mode == mode


class TestCompletionModeResolution:
    """Completion mode is resolved from QIIME command token position."""

    @pytest.mark.parametrize(
        ("text_with_cursor", "mode", "token_index"),
        [
            ("echo <CURSOR>hello", CompletionMode.NONE, -1),
            ("qii<CURSOR>me info", CompletionMode.NONE, 0),
            ("qiime <CURSOR>", CompletionMode.ROOT, 1),
            ("qiime inf<CURSOR>", CompletionMode.ROOT, 1),
            ("qiime info <CURSOR>", CompletionMode.PLUGIN, 2),
            ("qiime info act<CURSOR>", CompletionMode.PLUGIN, 2),
            ("qiime info action <CURSOR>", CompletionMode.PARAMETER, 3),
            ("qiime info action --h<CURSOR>", CompletionMode.PARAMETER, 3),
        ],
    )
    def test_completion_mode_from_document_analysis(
        self, text_with_cursor: str, mode: CompletionMode, token_index: int
    ) -> None:
        text, offset = extract_cursor_offset(text_with_cursor=text_with_cursor)

        ctx = get_completion_context(text, offset)

        assert ctx.mode == mode
        assert ctx.token_index == token_index


class TestToMergedOffsetCompat:
    """Test public offset conversion between original and merged text."""

    def test_offset_at_beginning(self) -> None:
        doc = analyze_document("qiime info")
        assert to_merged_offset(doc, 0) == 0

    def test_offset_in_middle(self) -> None:
        doc = analyze_document("qiime info")
        assert to_merged_offset(doc, 3) == 3

    def test_offset_at_end(self) -> None:
        doc = analyze_document("qiime info")
        assert to_merged_offset(doc, len("qiime info")) == len(doc.merged_text)

    def test_offset_beyond_end(self) -> None:
        doc = analyze_document("qiime info")
        assert to_merged_offset(doc, 100) == len(doc.merged_text)

    def test_offset_with_continuation_shift(self) -> None:
        doc = analyze_document("ab\\\ncd")
        assert to_merged_offset(doc, 4) == 2

    def test_offset_before_continuation(self) -> None:
        doc = analyze_document("ab\\\ncd")
        assert to_merged_offset(doc, 0) == 0
        assert to_merged_offset(doc, 1) == 1

    def test_offset_in_continuation_gap(self) -> None:
        doc = analyze_document("ab\\\ncd")
        assert to_merged_offset(doc, 2) == 2


class TestGetCompletionContext:
    """Integration tests for main entry point."""

    def test_cursor_outside_qiime_command(self) -> None:
        """Cursor outside qiime command should have mode=NONE."""
        text, offset = extract_cursor_offset(text_with_cursor="echo hel<CURSOR>lo")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.NONE
        assert ctx.command is None
        assert ctx.current_token is None
        assert ctx.token_index == -1

    def test_cursor_outside_qiime_command_at_end(self) -> None:
        """Cursor after non-qiime command should have mode=NONE."""
        text, offset = extract_cursor_offset(text_with_cursor="echo hello<CURSOR>")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.NONE

    def test_cursor_at_plugin_position(self) -> None:
        """Cursor at plugin position should have mode=ROOT."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime <CURSOR>")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.ROOT
        assert ctx.token_index == 1
        assert ctx.prefix == ""
        assert ctx.current_token is None

    def test_cursor_at_plugin_position_partial(self) -> None:
        """Cursor in partial plugin name should have mode=ROOT."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime inf<CURSOR>")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.ROOT
        assert ctx.token_index == 1
        assert ctx.prefix == "inf"
        assert ctx.current_token is not None
        assert ctx.current_token.text == "inf"

    def test_cursor_at_action_position(self) -> None:
        """Cursor at action position should have mode=PLUGIN."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime info <CURSOR>")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.PLUGIN
        assert ctx.token_index == 2
        assert ctx.prefix == ""
        assert ctx.current_token is None

    def test_cursor_at_action_position_partial(self) -> None:
        """Cursor in partial action name should have mode=PLUGIN."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime info act<CURSOR>")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.PLUGIN
        assert ctx.token_index == 2
        assert ctx.prefix == "act"
        assert ctx.current_token is not None
        assert ctx.current_token.text == "act"

    def test_cursor_at_parameter_position(self) -> None:
        """Cursor at parameter position should have mode=PARAMETER."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime info action <CURSOR>"
        )
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.PARAMETER
        assert ctx.token_index == 3
        assert ctx.prefix == ""
        assert ctx.current_token is None

    def test_cursor_at_parameter_position_partial(self) -> None:
        """Cursor in partial parameter name should have mode=PARAMETER."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime info action --h<CURSOR>"
        )
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.PARAMETER
        assert ctx.token_index == 3
        assert ctx.prefix == "--h"
        assert ctx.current_token is not None
        assert ctx.current_token.text == "--h"

    def test_cursor_on_qiime_token(self) -> None:
        """Cursor on 'qiime' token should have mode=NONE."""
        text, offset = extract_cursor_offset(text_with_cursor="qii<CURSOR>me info")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.NONE
        assert ctx.token_index == 0
        assert ctx.prefix == "qii"

    def test_cursor_at_start_of_qiime(self) -> None:
        """Cursor at start of qiime should have mode=NONE."""
        text, offset = extract_cursor_offset(text_with_cursor="<CURSOR>qiime info")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.NONE
        assert ctx.token_index == 0

    def test_with_line_continuation(self) -> None:
        """Line continuations should be handled correctly."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime \\\ninfo <CURSOR>")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.PLUGIN
        assert ctx.token_index == 2

    def test_with_line_continuation_at_plugin(self) -> None:
        """Line continuation at plugin position."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime \\\n<CURSOR>")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.ROOT

    def test_with_multiple_line_continuations(self) -> None:
        """Multiple line continuations should be handled."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime \\\ninfo \\\naction <CURSOR>"
        )
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.PARAMETER
        assert ctx.token_index == 3

    def test_command_after_semicolon(self) -> None:
        """Commands after semicolon should be detected."""
        text, offset = extract_cursor_offset(text_with_cursor="echo hi; qiime <CURSOR>")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.ROOT

    def test_command_after_pipe(self) -> None:
        """Commands after pipe should be detected."""
        text, offset = extract_cursor_offset(
            text_with_cursor="cat file | qiime <CURSOR>"
        )
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.ROOT

    def test_command_after_and_separator(self) -> None:
        """Commands after && should complete from root."""
        text, offset = extract_cursor_offset(text_with_cursor="true && qiime <CURSOR>")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.ROOT
        assert ctx.token_index == 1
        assert ctx.prefix == ""
        assert ctx.current_token is None

    def test_command_after_or_separator(self) -> None:
        """Commands after || should preserve plugin-position context."""
        text, offset = extract_cursor_offset(
            text_with_cursor="false || qiime info <CURSOR>"
        )
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.PLUGIN
        assert ctx.token_index == 2
        assert ctx.prefix == ""
        assert ctx.current_token is None
        assert ctx.command is not None
        assert [token.text for token in ctx.command.tokens] == ["qiime", "info"]

    def test_command_after_newline(self) -> None:
        """Commands after newline should complete from root."""
        text, offset = extract_cursor_offset(text_with_cursor="echo hi\nqiime <CURSOR>")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.ROOT
        assert ctx.token_index == 1
        assert ctx.prefix == ""
        assert ctx.current_token is None

    def test_quoted_separator_does_not_start_command(self) -> None:
        """Separators inside quotes should not affect qiime command detection."""
        text, offset = extract_cursor_offset(
            text_with_cursor="echo '; qiime'; qiime <CURSOR>"
        )
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.ROOT
        assert ctx.token_index == 1
        assert ctx.prefix == ""
        assert ctx.current_token is None

    def test_negative_offset_uses_start_of_document(self) -> None:
        """Negative offsets currently resolve like the start of the document."""
        ctx = get_completion_context("qiime ", -1)
        assert ctx.mode == CompletionMode.NONE
        assert ctx.token_index == 0

    def test_offset_past_end_uses_end_of_document(self) -> None:
        """Offsets past the document currently resolve like the document end."""
        ctx = get_completion_context("qiime ", 999)
        assert ctx.mode == CompletionMode.ROOT
        assert ctx.token_index == 1
        assert ctx.prefix == ""
        assert ctx.current_token is None

    def test_multiple_parameters(self) -> None:
        """Multiple parameters should all be in PARAMETER mode."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime info action --p1 val1 --p<CURSOR>2"
        )
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.PARAMETER
        assert ctx.token_index == 5
        assert ctx.prefix == "--p"

    def test_cursor_between_commands(self) -> None:
        """Cursor between qiime commands should detect the second."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime info; qiime <CURSOR>"
        )
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.ROOT

    def test_empty_text(self) -> None:
        """Empty text should return NONE mode."""
        text, offset = extract_cursor_offset(text_with_cursor="<CURSOR>")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.NONE
        assert ctx.command is None
        assert ctx.current_token is None

    def test_only_spaces(self) -> None:
        """Only spaces should return NONE mode."""
        text, offset = extract_cursor_offset(text_with_cursor=" <CURSOR>  ")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.NONE
        assert ctx.command is None

    def test_command_context_available(self) -> None:
        """Command context should be available when in qiime command."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime info action<CURSOR>"
        )
        ctx = get_completion_context(text, offset)
        assert ctx.command is not None
        assert ctx.command.tokens[0].text == "qiime"
        assert ctx.command.tokens[1].text == "info"
        assert ctx.command.tokens[2].text == "action"

    def test_token_positions_in_context(self) -> None:
        """Token positions should be correctly set in context."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime in<CURSOR>fo")
        ctx = get_completion_context(text, offset)
        assert ctx.current_token is not None
        assert ctx.current_token.start == 6
        assert ctx.current_token.end == 10

    def test_prefix_extraction_middle_of_token(self) -> None:
        """Prefix should be text before cursor in current token."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime dem<CURSOR>ux")
        ctx = get_completion_context(text, offset)
        assert ctx.prefix == "dem"
        assert ctx.current_token is not None
        assert ctx.current_token.text == "demux"

    def test_prefix_at_token_start(self) -> None:
        """Prefix at token start should be empty."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime <CURSOR>")
        ctx = get_completion_context(text, offset)
        assert ctx.prefix == ""
        assert ctx.current_token is None

    def test_token_index_at_end_of_command(self) -> None:
        """Token index at end of command should be number of tokens."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime info action <CURSOR>"
        )
        ctx = get_completion_context(text, offset)
        assert ctx.token_index == 3
        assert ctx.mode == CompletionMode.PARAMETER
