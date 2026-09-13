"""Source mapping and cursor facts, independent of LSP and QIIME discovery."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from q2lsp.core.document import analyze_document
from tests.helpers.cursor import extract_cursor_offset


@pytest.mark.parametrize(
    ("source", "merged", "words"),
    [
        ("", "", []),
        ("echo hello", "echo hello", []),
        ("qiime info", "qiime info", [["qiime", "info"]]),
        (
            "qiime info\r\nqiime tools",
            "qiime info\r\nqiime tools",
            [["qiime", "info"], ["qiime", "tools"]],
        ),
        ("qiime \\\r\ninfo", "qiime info", [["qiime", "info"]]),
        ("qiime \\\ninfo", "qiime info", [["qiime", "info"]]),
        (
            "echo hi; qiime info --help; qiime tools import",
            "echo hi; qiime info --help; qiime tools import",
            [["qiime", "info", "--help"], ["qiime", "tools", "import"]],
        ),
    ],
)
def test_document_snapshot(source: str, merged: str, words: list[list[str]]) -> None:
    document = analyze_document(source)
    assert document.source == source
    assert document.merged_text == merged
    assert len(document.offset_map) == len(merged) + 1
    assert [
        [token.text for token in command.tokens] for command in document.commands
    ] == words


def test_command_and_token_spans_use_merged_offsets() -> None:
    document = analyze_document("qiime\\\n info --help")
    (command,) = document.commands
    assert (command.start, command.end) == (0, 17)
    assert [(token.text, token.start, token.end) for token in command.tokens] == [
        ("qiime", 0, 5),
        ("info", 6, 10),
        ("--help", 11, 17),
    ]
    document = analyze_document("echo hi; qiime info --help; qiime tools import")
    assert [(command.start, command.end) for command in document.commands] == [
        (9, 26),
        (28, 46),
    ]


@pytest.mark.parametrize(
    ("source", "merged", "original"),
    [
        ("qiime info", 0, 0),
        ("qiime info", 5, 5),
        ("qiime \\\ninfo", 6, 8),
        ("qiime\\\n info", 5, 7),
        ("qiime\\\n info", 10, 12),
        ("qiime\\\n tools\\\n import", 6, 8),
        ("qiime\\\n tools\\\n import", 12, 16),
        ("qiime\\\n tools\\\n import", 18, 22),
    ],
)
def test_offset_mapping(source: str, merged: int, original: int) -> None:
    document = analyze_document(source)
    assert document.original_offset(merged) == original
    assert document.merged_offset(original) == merged


@pytest.mark.parametrize(
    ("source", "offset", "merged"),
    [
        ("qiime \\\ninfo", 6, 6),
        ("qiime \\\ninfo", 7, 6),
        ("qiime\\\n info", 5, 5),
        ("qiime\\\n info", 6, 5),
        ("qiime\\\n info", 7, 5),
        ("qiime\\\n tools\\\n import", 13, 11),
        ("qiime\\\n tools\\\n import", 14, 11),
        ("qiime\\\n tools\\\n import", 15, 11),
        ("qiime info", 100, 10),
    ],
)
def test_continuation_gaps_and_past_eof(source: str, offset: int, merged: int) -> None:
    assert analyze_document(source).merged_offset(offset) == merged


def test_invalid_offsets() -> None:
    document = analyze_document("qiime info")
    with pytest.raises(ValueError, match="non-negative"):
        document.original_offset(-1)
    with pytest.raises(ValueError, match="non-negative"):
        document.merged_offset(-1)
    with pytest.raises(ValueError, match="exceeds"):
        document.original_offset(9999)


def test_half_open_span_does_not_include_following_continuation() -> None:
    document = analyze_document("qiime\\\n info")
    assert document.original_span(0, 5) == (0, 5)
    assert document.original_span(6, 10) == (8, 12)
    assert document.original_span(5, 5) == (7, 7)
    assert document.command_text(document.commands[0]) == document.source


@pytest.mark.parametrize(
    ("source", "index", "prefix", "token"),
    [
        ("echo hel<CURSOR>lo", -1, "", None),
        ("echo hello<CURSOR>", -1, "", None),
        ("<CURSOR>", -1, "", None),
        (" <CURSOR>  ", -1, "", None),
        ("qiime <CURSOR>", 1, "", None),
        ("qiime inf<CURSOR>", 1, "inf", "inf"),
        ("qiime inf<CURSOR>\r\n", 1, "inf", "inf"),
        ("qiime inf<CURSOR>\n", 1, "inf", "inf"),
        ("qiime inf<CURSOR>; echo ok", 1, "inf", "inf"),
        ("qiime info;<CURSOR> echo ok", -1, "", None),
        ("qiime in<CURSOR>fo", 1, "in", "info"),
        ('qiime "in<CURSOR>fo"', 1, "in", "info"),
        ("qiime 'in<CURSOR>fo'", 1, "in", "info"),
        ("qiime dem<CURSOR>ux", 1, "dem", "demux"),
        ("qiime info <CURSOR>", 2, "", None),
        ("qiime info act<CURSOR>", 2, "act", "act"),
        ("qiime info action<CURSOR>", 2, "action", "action"),
        ("qiime info action <CURSOR>", 3, "", None),
        ("qiime info action --h<CURSOR>", 3, "--h", "--h"),
        ("qii<CURSOR>me info", 0, "qii", "qiime"),
        ("<CURSOR>qiime info", 0, "", "qiime"),
        ("qiime \\\ninfo <CURSOR>", 2, "", None),
        ("qiime \\\n<CURSOR>", 1, "", None),
        ("qiime \\\ninfo \\\naction <CURSOR>", 3, "", None),
        ("echo hi; qiime <CURSOR>", 1, "", None),
        ("cat file | qiime <CURSOR>", 1, "", None),
        ("true && qiime <CURSOR>", 1, "", None),
        ("false || qiime info <CURSOR>", 2, "", None),
        ("echo hi\nqiime <CURSOR>", 1, "", None),
        ("echo '; qiime'; qiime <CURSOR>", 1, "", None),
        ("qiime info action --p1 val1 --p<CURSOR>2", 5, "--p", "--p2"),
        ("qiime info; qiime <CURSOR>", 1, "", None),
        ("qiime info --hel<CURSOR>p", 2, "--hel", "--help"),
        ("run_cmd qiime <CURSOR>", 1, "", None),
        ("qiime  <CURSOR> info action", 1, "", None),
        ("qiime info  <CURSOR> action --help", 2, "", None),
    ],
)
def test_cursor_facts(source: str, index: int, prefix: str, token: str | None) -> None:
    text, offset = extract_cursor_offset(text_with_cursor=source)
    context = analyze_document(text).cursor_at(offset)
    assert context.token_index == index
    assert context.prefix == prefix
    assert (context.current_token.text if context.current_token else None) == token
    if index == -1:
        assert context.command is None
    else:
        assert context.command is not None
        assert context.command.tokens[0].text == "qiime"


def test_cursor_offset_clamping_and_token_span() -> None:
    document = analyze_document("qiime info")
    assert document.cursor_at(-1) == document.cursor_at(0)
    assert document.cursor_at(999) == document.cursor_at(len(document.source))
    context = document.cursor_at(8)
    assert context.current_token is not None
    assert (context.current_token.start, context.current_token.end) == (6, 10)
    assert analyze_document("qiime ").cursor_at(999).token_index == 1


def test_cursor_across_continuation_boundary() -> None:
    document = analyze_document("qiime \\\ninfo action --help")
    assert [
        document.cursor_at(offset).token_index
        for offset in (0, 6, 8, len(document.source))
    ] == [0, 1, 1, 3]


def test_snapshot_and_syntax_are_immutable() -> None:
    document = analyze_document("qiime info")
    command = document.commands[0]
    with pytest.raises(FrozenInstanceError):
        setattr(document, "source", "changed")
    with pytest.raises(FrozenInstanceError):
        setattr(command, "start", 42)
    with pytest.raises(FrozenInstanceError):
        setattr(command.tokens[0], "text", "changed")
    assert isinstance(command.tokens, tuple)
