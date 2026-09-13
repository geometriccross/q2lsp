"""Hover routing and rendering through the same help-provider path as production."""

from __future__ import annotations

import pytest
from lsprotocol import types
from pygls.workspace import TextDocument

from q2lsp.lsp.adapter import offset_to_position
from q2lsp.lsp.hover_handler import handle_hover
from tests.helpers.cursor import extract_cursor_offset


@pytest.mark.parametrize(
    ("source", "expected_path"),
    [
        ("qii<CURSOR>me info", []),
        ("qiime fe<CURSOR>ature-table summarize", ["feature-table"]),
        ("qiime feature-table sum<CURSOR>marize", ["feature-table", "summarize"]),
        ("qiime in<CURSOR>fo", ["info"]),
        ("qiime \\\nfe<CURSOR>ature-table summarize", ["feature-table"]),
    ],
)
def test_hover_requests_cli_help_and_returns_fenced_markdown(
    source: str,
    expected_path: list[str],
) -> None:
    text, offset = extract_cursor_offset(text_with_cursor=source)
    document = TextDocument(uri="file:///test.sh", source=text)
    calls: list[list[str]] = []
    help_text = (
        "Usage: qiime [OPTIONS] COMMAND [ARGS]...\n\nOptions:\n  --help  Show help."
    )

    def get_help(path: list[str]) -> str:
        calls.append(path)
        return help_text

    hover = handle_hover(document, offset_to_position(document, offset), get_help)
    assert calls == [expected_path]
    assert hover == types.Hover(
        contents=types.MarkupContent(
            kind=types.MarkupKind.Markdown,
            value=f"```\n{help_text}\n```",
        )
    )


@pytest.mark.parametrize(
    "source",
    [
        "qiime  <CURSOR> info",
        "echo <CURSOR>hello",
        "qiime feature-table summarize --<CURSOR>help",
        "qiime feature-table summarize --i-table ta<CURSOR>ble.qza",
        "qiime feature-table summarize --help <CURSOR>",
    ],
)
def test_hover_outside_command_path_does_not_request_help(source: str) -> None:
    text, offset = extract_cursor_offset(text_with_cursor=source)
    document = TextDocument(uri="file:///test.sh", source=text)

    def fail_help(path: list[str]) -> str | None:
        raise AssertionError(f"Unexpected help request: {path}")

    assert (
        handle_hover(document, offset_to_position(document, offset), fail_help) is None
    )


def test_hover_returns_none_when_help_is_unavailable() -> None:
    document = TextDocument(uri="file:///test.sh", source="qiime unknown")
    assert handle_hover(document, types.Position(0, 8), lambda _path: None) is None
