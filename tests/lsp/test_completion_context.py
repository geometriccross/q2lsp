"""Tests for completion context determination."""

from __future__ import annotations

import pytest

from tests.helpers.cursor import extract_cursor_offset

from q2lsp.lsp.document_commands import analyze_document, to_merged_offset
from q2lsp.lsp.types import CompletionMode
from tests.helpers.completions import get_completion_context


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


class TestOriginalToMergedOffset:
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
