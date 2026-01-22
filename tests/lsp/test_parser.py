"""Tests for shell parser."""

from __future__ import annotations

from q2lsp.lsp.parser import (
    merge_line_continuations,
    tokenize_shell_line,
    find_qiime_commands,
    command_at_position,
    get_completion_context,
)
from q2lsp.lsp.types import TokenSpan, ParsedCommand, CompletionContext


class TestMergeLineContinuations:
    def test_no_continuation(self) -> None:
        text = "qiime info --help"
        merged, offset_map = merge_line_continuations(text)
        assert merged == text
        assert len(offset_map) == len(merged) + 1

    def test_single_continuation(self) -> None:
        text = "qiime \\\ninfo"
        merged, offset_map = merge_line_continuations(text)
        assert merged == "qiime info"
        assert len(offset_map) == len(merged) + 1

    def test_multiple_continuations(self) -> None:
        text = "qiime \\\ninfo \\\n--help"
        merged, offset_map = merge_line_continuations(text)
        assert merged == "qiime info --help"

    def test_offset_map_boundaries(self) -> None:
        text = "ab\\\ncd"
        merged, offset_map = merge_line_continuations(text)
        assert merged == "abcd"
        # offset_map[0]=0 (a), [1]=1 (b), [2]=4 (c), [3]=5 (d), [4]=6 (end)
        assert offset_map[0] == 0
        assert offset_map[1] == 1
        assert offset_map[2] == 4
        assert offset_map[3] == 5


class TestTokenizeShellLine:
    def test_simple_tokens(self) -> None:
        tokens = tokenize_shell_line("qiime info --help", 0)
        assert len(tokens) == 3
        assert tokens[0].text == "qiime"
        assert tokens[1].text == "info"
        assert tokens[2].text == "--help"

    def test_token_positions(self) -> None:
        tokens = tokenize_shell_line("qiime info", 0)
        assert tokens[0].start == 0
        assert tokens[0].end == 5
        assert tokens[1].start == 6
        assert tokens[1].end == 10

    def test_single_quotes(self) -> None:
        tokens = tokenize_shell_line("qiime 'hello world'", 0)
        assert len(tokens) == 2
        assert tokens[1].text == "hello world"

    def test_single_quotes_no_escape(self) -> None:
        tokens = tokenize_shell_line(r"qiime 'hello\nworld'", 0)
        assert tokens[1].text == r"hello\nworld"

    def test_double_quotes(self) -> None:
        tokens = tokenize_shell_line('qiime "hello world"', 0)
        assert len(tokens) == 2
        assert tokens[1].text == "hello world"

    def test_double_quotes_escape(self) -> None:
        tokens = tokenize_shell_line(r'qiime "hello\"world"', 0)
        assert tokens[1].text == 'hello"world'

    def test_unquoted_escape(self) -> None:
        tokens = tokenize_shell_line(r"qiime\ info", 0)
        assert len(tokens) == 1
        assert tokens[0].text == "qiime info"

    def test_with_offset(self) -> None:
        tokens = tokenize_shell_line("qiime info", 10)
        assert tokens[0].start == 10
        assert tokens[0].end == 15


class TestFindQiimeCommands:
    def test_simple_qiime_command(self) -> None:
        cmds = find_qiime_commands("qiime info")
        assert len(cmds) == 1
        assert cmds[0].tokens[0].text == "qiime"

    def test_qiime_after_semicolon(self) -> None:
        cmds = find_qiime_commands("echo hi; qiime info")
        assert len(cmds) == 1
        assert cmds[0].tokens[0].text == "qiime"

    def test_qiime_after_pipe(self) -> None:
        cmds = find_qiime_commands("cat file | qiime info")
        assert len(cmds) == 1

    def test_qiime_after_and(self) -> None:
        cmds = find_qiime_commands("true && qiime info")
        assert len(cmds) == 1

    def test_qiime_after_or(self) -> None:
        cmds = find_qiime_commands("false || qiime info")
        assert len(cmds) == 1

    def test_no_qiime_command(self) -> None:
        cmds = find_qiime_commands("echo hello")
        assert len(cmds) == 0

    def test_multiple_qiime_commands(self) -> None:
        cmds = find_qiime_commands("qiime info; qiime tools")
        assert len(cmds) == 2

    def test_non_first_token_qiime(self) -> None:
        # "sudo qiime" should NOT be detected (first token must be "qiime")
        cmds = find_qiime_commands("sudo qiime info")
        assert len(cmds) == 0


class TestCommandAtPosition:
    def test_cursor_in_command(self) -> None:
        cmds = find_qiime_commands("qiime info")
        cmd = command_at_position(cmds, 3)
        assert cmd is not None

    def test_cursor_at_command_start(self) -> None:
        cmds = find_qiime_commands("qiime info")
        cmd = command_at_position(cmds, 0)
        assert cmd is not None

    def test_cursor_outside_command(self) -> None:
        cmds = find_qiime_commands("echo hi; qiime info")
        cmd = command_at_position(cmds, 3)  # In "echo"
        assert cmd is None


class TestGetCompletionContext:
    def test_mode_root_after_qiime(self) -> None:
        ctx = get_completion_context("qiime ", 6)
        assert ctx.mode == "root"
        assert ctx.token_index == 1

    def test_mode_root_partial_plugin(self) -> None:
        ctx = get_completion_context("qiime inf", 9)
        assert ctx.mode == "root"
        assert ctx.prefix == "inf"

    def test_mode_plugin_after_plugin(self) -> None:
        ctx = get_completion_context("qiime info ", 11)
        assert ctx.mode == "plugin"
        assert ctx.token_index == 2

    def test_mode_plugin_at_token2(self) -> None:
        # Token 2 (action position) should be "plugin" mode
        ctx = get_completion_context("qiime info --help", 17)
        assert ctx.mode == "plugin"
        assert ctx.token_index == 2

    def test_mode_parameter(self) -> None:
        # "qiime info action --help" has 4 tokens
        # token 3 (--help) should be parameter mode
        ctx = get_completion_context("qiime info action --help", 24)
        assert ctx.mode == "parameter"

    def test_mode_none_outside_qiime(self) -> None:
        ctx = get_completion_context("echo hello", 5)
        assert ctx.mode == "none"

    def test_mode_none_on_qiime_token(self) -> None:
        ctx = get_completion_context("qiime info", 3)
        assert ctx.mode == "none"  # Cursor on "qiime" itself

    def test_with_line_continuation(self) -> None:
        ctx = get_completion_context("qiime \\\ninfo ", 13)
        # After merging: "qiime info " - cursor at position after "info"
        assert ctx.mode == "plugin"

    def test_prefix_extraction(self) -> None:
        ctx = get_completion_context("qiime inf", 9)
        assert ctx.prefix == "inf"
        assert ctx.current_token is not None
        assert ctx.current_token.text == "inf"
