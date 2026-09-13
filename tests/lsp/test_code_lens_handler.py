"""Behavior tests for standalone code lens handler."""

from __future__ import annotations

from lsprotocol import types
from q2lsp.core.document import Document, analyze_document
from q2lsp.lsp.features import handle_code_lens


def _document(source: str) -> Document:
    return analyze_document(source)


def test_handle_code_lens_returns_code_lens_for_qiime_command() -> None:
    """Code lens returns a run command action for a QIIME command."""
    code_lenses = handle_code_lens(_document("qiime info"), "file:///test.sh")

    assert len(code_lenses) == 1
    code_lens = code_lenses[0]
    assert code_lens.range == types.Range(
        start=types.Position(line=0, character=0),
        end=types.Position(line=0, character=5),
    )
    assert code_lens.command is not None
    assert code_lens.command.title == "Run QIIME command"
    assert code_lens.command.command == "q2lsp.runCommand"


def test_handle_code_lens_returns_empty_list_for_no_qiime_commands() -> None:
    """Code lens returns no actions when the document has no QIIME commands."""
    assert handle_code_lens(_document("echo hello"), "file:///test.sh") == []


def test_handle_code_lens_carries_tokens_and_shell_text() -> None:
    """Code lens arguments include the document URI, raw shell text, and tokens."""
    code_lenses = handle_code_lens(
        _document('qiime feature-table summarize --i-table "$TABLE"'), "file:///test.sh"
    )

    assert len(code_lenses) == 1
    command = code_lenses[0].command
    assert command is not None
    assert command.arguments == [
        {
            "uri": "file:///test.sh",
            "commandText": 'qiime feature-table summarize --i-table "$TABLE"',
            "tokens": [
                "qiime",
                "feature-table",
                "summarize",
                "--i-table",
                "$TABLE",
            ],
        }
    ]
