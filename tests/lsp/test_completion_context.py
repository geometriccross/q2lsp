"""Tests for completion context determination."""

from __future__ import annotations

from tests.helpers.cursor import extract_cursor_offset

from q2lsp.lsp.completion_context import (
    _determine_mode,
    _original_to_merged_offset,
    get_completion_context,
)
from q2lsp.lsp.types import CompletionMode


class TestDetermineMode:
    """Test mode determination logic."""

    def test_negative_token_index(self) -> None:
        """token_index < 0 should return NONE."""
        mode = _determine_mode(-1)
        assert mode == CompletionMode.NONE

    def test_negative_token_index_two(self) -> None:
        """token_index = -5 should return NONE."""
        mode = _determine_mode(-5)
        assert mode == CompletionMode.NONE

    def test_token_index_zero(self) -> None:
        """token_index == 0 (on 'qiime') should return NONE."""
        mode = _determine_mode(0)
        assert mode == CompletionMode.NONE

    def test_token_index_one(self) -> None:
        """token_index == 1 (plugin position) should return ROOT."""
        mode = _determine_mode(1)
        assert mode == CompletionMode.ROOT

    def test_token_index_two(self) -> None:
        """token_index == 2 (action position) should return PLUGIN."""
        mode = _determine_mode(2)
        assert mode == CompletionMode.PLUGIN

    def test_token_index_three(self) -> None:
        """token_index == 3 (parameter position) should return PARAMETER."""
        mode = _determine_mode(3)
        assert mode == CompletionMode.PARAMETER

    def test_token_index_four(self) -> None:
        """token_index == 4 (parameter position) should return PARAMETER."""
        mode = _determine_mode(4)
        assert mode == CompletionMode.PARAMETER

    def test_token_index_large(self) -> None:
        """token_index >= 3 should return PARAMETER."""
        mode = _determine_mode(10)
        assert mode == CompletionMode.PARAMETER


class TestOriginalToMergedOffset:
    """Test offset conversion between original and merged text."""

    def test_offset_at_beginning(self) -> None:
        """Offset at position 0 should map to position 0."""
        offset_map = [0, 1, 2, 3, 4]
        merged_offset = _original_to_merged_offset(0, offset_map)
        assert merged_offset == 0

    def test_offset_in_middle(self) -> None:
        """Offset in middle should map correctly."""
        offset_map = [0, 1, 2, 3, 4, 5, 6]
        merged_offset = _original_to_merged_offset(3, offset_map)
        assert merged_offset == 3

    def test_offset_at_end(self) -> None:
        """Offset at end should map to last valid index."""
        offset_map = [0, 1, 2, 3, 4]
        merged_offset = _original_to_merged_offset(4, offset_map)
        assert merged_offset == 4

    def test_offset_beyond_end(self) -> None:
        """Offset beyond end should return last index - 1."""
        offset_map = [0, 1, 2, 3, 4, 5]
        merged_offset = _original_to_merged_offset(100, offset_map)
        assert merged_offset == 5

    def test_offset_with_continuation_shift(self) -> None:
        """Offsets should adjust for line continuation removal."""
        # Original: "ab\\\ncd" (length 6)
        # Merged:   "abcd" (length 4)
        # offset_map: [0, 1, 4, 5, 6] maps merged to original positions
        offset_map = [0, 1, 4, 5, 6]
        # Original offset 4 (which is 'c' in merged) -> merged offset 2
        merged_offset = _original_to_merged_offset(4, offset_map)
        assert merged_offset == 2

    def test_offset_before_continuation(self) -> None:
        """Offset before continuation should map 1:1."""
        offset_map = [0, 1, 4, 5, 6]
        merged_offset = _original_to_merged_offset(0, offset_map)
        assert merged_offset == 0

        merged_offset = _original_to_merged_offset(1, offset_map)
        assert merged_offset == 1

    def test_offset_in_continuation_gap(self) -> None:
        """Offset in continuation gap maps to after gap."""
        offset_map = [0, 1, 4, 5, 6]
        # Original offset 2 is in the gap (part of '\\\n')
        # Should map to merged offset 2 (after gap starts)
        merged_offset = _original_to_merged_offset(2, offset_map)
        assert merged_offset == 2


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
