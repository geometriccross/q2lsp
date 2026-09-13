"""Behavior tests for standalone completion handler."""

from __future__ import annotations

from lsprotocol import types
from q2lsp.core.document import Document, analyze_document
from q2lsp.lsp.features import handle_completion
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.types import CommandHierarchy


def _document(source: str) -> Document:
    return analyze_document(source)


def test_handle_completion_returns_items_for_known_hierarchy() -> None:
    """Completion returns catalog-backed LSP items for a known hierarchy."""
    hierarchy: CommandHierarchy = {
        "qiime": {
            "name": "qiime",
            "help": "QIIME root help",
            "builtins": ["info"],
            "info": {
                "name": "info",
                "short_help": "Display deployment information",
                "type": "builtin",
            },
            "feature-table": {
                "name": "feature-table",
                "short_description": "Feature table plugin",
            },
        }
    }

    completion = handle_completion(
        _document("qiime "),
        types.Position(line=0, character=6),
        lambda: QiimeCatalog.from_hierarchy(hierarchy),
    )

    assert isinstance(completion, types.CompletionList)
    assert completion.is_incomplete is False
    assert [item.label for item in completion.items] == ["info", "feature-table"]
    assert [item.kind for item in completion.items] == [
        types.CompletionItemKind.Class,
        types.CompletionItemKind.Module,
    ]


def test_handle_completion_returns_empty_list_for_empty_prefix_on_empty_hierarchy() -> (
    None
):
    """Completion returns no items when the catalog has no commands."""
    hierarchy: CommandHierarchy = {"qiime": {"name": "qiime", "builtins": []}}

    completion = handle_completion(
        _document("qiime "),
        types.Position(line=0, character=6),
        lambda: QiimeCatalog.from_hierarchy(hierarchy),
    )

    assert completion == types.CompletionList(is_incomplete=False, items=[])
