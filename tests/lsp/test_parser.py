from __future__ import annotations

from q2lsp.lsp.parser import (
    collect_continued_lines,
    find_qiime_command_start,
    parse_context,
    tokenize_shell,
)


def test_collect_continued_lines_no_continuation() -> None:
    lines = ["qiime tools import --input-path data --output-path output"]
    result, start_idx = collect_continued_lines(lines, 0)

    assert result == "qiime tools import --input-path data --output-path output"
    assert start_idx == 0


def test_collect_continued_lines_with_continuation() -> None:
    lines = [
        "qiime tools import \\",
        "  --input-path data \\",
        "  --output-path output",
    ]
    result, start_idx = collect_continued_lines(lines, 2)

    assert result == "qiime tools import --input-path data --output-path output"
    assert start_idx == 0


def test_collect_continued_lines_cursor_at_middle() -> None:
    lines = [
        "qiime tools import \\",
        "  --input-path data \\",
        "  --output-path output",
    ]
    result, start_idx = collect_continued_lines(lines, 1)

    assert result == "qiime tools import --input-path data"
    assert start_idx == 0


def test_collect_continued_lines_spaces_before_backslash() -> None:
    lines = ["qiime tools import --input-path data   \\  ", "--output-path output"]
    result, start_idx = collect_continued_lines(lines, 1)

    # Should rstrip before checking for backslash
    assert result == "qiime tools import --input-path data --output-path output"
    assert start_idx == 0


def test_tokenize_shell_simple() -> None:
    line = "qiime tools import"
    tokens = tokenize_shell(line)

    assert len(tokens) == 3
    assert tokens[0]["text"] == "qiime"
    assert tokens[0]["start"] == 0
    assert tokens[0]["end"] == 5
    assert tokens[1]["text"] == "tools"
    assert tokens[1]["start"] == 6
    assert tokens[1]["end"] == 11
    assert tokens[2]["text"] == "import"
    assert tokens[2]["start"] == 12
    assert tokens[2]["end"] == 18


def test_tokenize_shell_single_quotes() -> None:
    line = "qiime 'tools import'"
    tokens = tokenize_shell(line)

    assert len(tokens) == 2
    assert tokens[0]["text"] == "qiime"
    assert tokens[1]["text"] == "tools import"
    assert tokens[1]["start"] == 6
    assert tokens[1]["end"] == 21


def test_tokenize_shell_double_quotes() -> None:
    line = 'qiime "tools import"'
    tokens = tokenize_shell(line)

    assert len(tokens) == 2
    assert tokens[0]["text"] == "qiime"
    assert tokens[1]["text"] == "tools import"
    assert tokens[1]["start"] == 6
    assert tokens[1]["end"] == 21


def test_tokenize_shell_backslash_escape() -> None:
    line = r"qiime\ tools\ import"
    tokens = tokenize_shell(line)

    assert len(tokens) == 1
    assert tokens[0]["text"] == "qiime tools import"
    assert tokens[0]["start"] == 0
    assert tokens[0]["end"] == 19


def test_tokenize_shell_double_quote_escape() -> None:
    line = r'qiime "tools\"import"'
    tokens = tokenize_shell(line)

    assert len(tokens) == 2
    assert tokens[0]["text"] == "qiime"
    assert tokens[1]["text"] == 'tools"import'


def test_tokenize_shell_empty_quotes() -> None:
    line = "qiime '' \"\""
    tokens = tokenize_shell(line)

    assert len(tokens) == 3
    assert tokens[0]["text"] == "qiime"
    assert tokens[1]["text"] == ""
    assert tokens[2]["text"] == ""


def test_find_qiime_command_start_simple() -> None:
    tokens = tokenize_shell("qiime tools import")
    result = find_qiime_command_start(tokens)

    assert result == 0


def test_find_qiime_command_start_with_semicolon() -> None:
    tokens = tokenize_shell("other command; qiime tools import")
    result = find_qiime_command_start(tokens)

    assert result == 3


def test_find_qiime_command_start_with_pipe() -> None:
    tokens = tokenize_shell("other command | qiime tools import")
    result = find_qiime_command_start(tokens)

    assert result == 3


def test_find_qiime_command_start_with_and() -> None:
    tokens = tokenize_shell("other command && qiime tools import")
    result = find_qiime_command_start(tokens)

    assert result == 3


def test_find_qiime_command_start_qiime_before_boundary() -> None:
    tokens = tokenize_shell("qiime tools import; other command")
    result = find_qiime_command_start(tokens)

    assert result is None


def test_find_qiime_command_start_no_qiime() -> None:
    tokens = tokenize_shell("other command")
    result = find_qiime_command_start(tokens)

    assert result is None


def test_parse_context_simple() -> None:
    lines = ["qiime tools import"]
    result = parse_context(lines, 0, 12)

    assert len(result["tokens"]) == 3
    assert result["current_token_index"] == 2
    assert result["cursor_offset"] == 12


def test_parse_context_with_continuation() -> None:
    lines = [
        "qiime tools \\",
        "  import",
    ]
    result = parse_context(lines, 1, 5)

    assert len(result["tokens"]) == 3
    assert result["current_token_index"] == 2
    # Cursor offset should be calculated correctly across continuations


def test_parse_context_cursor_in_whitespace() -> None:
    lines = ["qiime  tools"]
    result = parse_context(lines, 0, 6)

    assert len(result["tokens"]) == 2
    assert result["current_token_index"] is None


def test_parse_context_cursor_at_end() -> None:
    lines = ["qiime tools import"]
    result = parse_context(lines, 0, 18)

    assert len(result["tokens"]) == 3
    assert result["current_token_index"] == 2
    assert result["cursor_offset"] == 18


def test_parse_context_cursor_at_start() -> None:
    lines = ["qiime tools import"]
    result = parse_context(lines, 0, 0)

    assert len(result["tokens"]) == 3
    assert result["current_token_index"] == 0
