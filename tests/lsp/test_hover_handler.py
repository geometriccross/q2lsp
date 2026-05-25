"""Behavior tests for standalone hover handler."""

from __future__ import annotations

from lsprotocol import types
from pygls.workspace import TextDocument

from q2lsp.lsp.hover_handler import handle_hover
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.types import CommandHierarchy


def _document(source: str) -> TextDocument:
    return TextDocument(
        uri="file:///test.sh",
        source=source,
        language_id="shellscript",
        version=1,
    )


def test_handle_hover_returns_help_for_root_token() -> None:
    """Hover returns fenced markdown help for the qiime root token."""
    hierarchy: CommandHierarchy = {
        "qiime": {
            "name": "qiime",
            "help": "QIIME root help",
            "builtins": [],
        }
    }

    hover = handle_hover(
        _document("qiime info"),
        types.Position(line=0, character=2),
        lambda: QiimeCatalog.from_hierarchy(hierarchy),
    )

    assert hover == types.Hover(
        contents=types.MarkupContent(
            kind=types.MarkupKind.Markdown,
            value="```\nQIIME root help\n```",
        )
    )


def test_handle_hover_returns_none_when_cursor_is_not_on_qiime_token() -> None:
    """Hover returns None outside qiime commands."""
    hierarchy: CommandHierarchy = {
        "qiime": {
            "name": "qiime",
            "help": "QIIME root help",
            "builtins": [],
        }
    }

    hover = handle_hover(
        _document("echo hello"),
        types.Position(line=0, character=2),
        lambda: QiimeCatalog.from_hierarchy(hierarchy),
    )

    assert hover is None
