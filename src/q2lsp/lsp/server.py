"""QIIME2 LSP Server using pygls 2.0.

Provides completion support for QIIME2 CLI commands in shell scripts.
"""

from __future__ import annotations

from lsprotocol import types
from pygls.lsp.server import LanguageServer
from pygls.workspace import TextDocument

from q2lsp.lsp.completions import CompletionItem as InternalCompletionItem
from q2lsp.lsp.completions import get_completions
from q2lsp.lsp.parser import get_completion_context
from q2lsp.qiime.types import CommandHierarchy


# Module-level cache for command hierarchy (expensive to build)
_hierarchy_cache: CommandHierarchy | None = None


def get_cached_hierarchy() -> CommandHierarchy:
    """
    Get or build the QIIME2 command hierarchy (cached).

    The hierarchy is built once on first access since importing
    q2cli and building the hierarchy is expensive.
    """
    global _hierarchy_cache
    if _hierarchy_cache is None:
        _hierarchy_cache = _build_hierarchy()
    return _hierarchy_cache


def _build_hierarchy() -> CommandHierarchy:
    """Build the QIIME2 command hierarchy from q2cli."""
    from q2cli.commands import RootCommand

    from q2lsp.qiime.command_hierarchy import build_command_hierarchy

    root = RootCommand()
    return build_command_hierarchy(root)


def create_server() -> LanguageServer:
    """
    Create and configure the LSP server.

    Returns:
        Configured LanguageServer instance with completion support.
    """
    server = LanguageServer("q2lsp", "v0.1.0")

    @server.feature(
        types.TEXT_DOCUMENT_COMPLETION,
        types.CompletionOptions(
            trigger_characters=[" ", "-"],
            resolve_provider=False,
        ),
    )
    def completion(params: types.CompletionParams) -> types.CompletionList:
        """
        Handle textDocument/completion requests.

        Provides completion for QIIME2 CLI commands in shell scripts.
        """
        document = server.workspace.get_text_document(params.text_document.uri)

        # Calculate document offset from line/character position
        offset = _position_to_offset(document, params.position)

        # Get completion context from parser
        ctx = get_completion_context(document.source, offset)

        # Get completion items
        hierarchy = get_cached_hierarchy()
        internal_items = get_completions(ctx, hierarchy)

        # Convert to LSP CompletionItems
        lsp_items = [_to_lsp_completion_item(item) for item in internal_items]

        return types.CompletionList(
            is_incomplete=False,
            items=lsp_items,
        )

    return server


def _position_to_offset(document: TextDocument, position: types.Position) -> int:
    """
    Convert LSP Position (line, character) to document offset.

    Args:
        document: The text document
        position: LSP position with 0-based line and character

    Returns:
        0-based offset in the document
    """
    lines = document.lines
    offset = 0

    # Add characters from all lines before current line
    for i in range(min(position.line, len(lines))):
        offset += len(
            lines[i]
        )  # lines already include newline characters (splitlines(True))

    # Add characters in current line up to cursor
    if position.line < len(lines):
        offset += min(position.character, len(lines[position.line]))

    return offset


def _to_lsp_completion_item(item: InternalCompletionItem) -> types.CompletionItem:
    """
    Convert internal CompletionItem to LSP CompletionItem.

    Args:
        item: Internal completion item

    Returns:
        LSP-compatible CompletionItem
    """
    return types.CompletionItem(
        label=item.label,
        detail=item.detail,
        kind=_completion_kind_from_string(item.kind),
        insert_text=item.insert_text if item.insert_text else None,
    )


def _completion_kind_from_string(kind: str) -> types.CompletionItemKind:
    """
    Map internal kind string to LSP CompletionItemKind.

    Args:
        kind: Internal kind string ("plugin", "action", "parameter", "builtin")

    Returns:
        LSP CompletionItemKind enum value
    """
    mapping = {
        "plugin": types.CompletionItemKind.Module,
        "action": types.CompletionItemKind.Function,
        "parameter": types.CompletionItemKind.Field,
        "builtin": types.CompletionItemKind.Class,
    }
    return mapping.get(kind, types.CompletionItemKind.Text)


def start_server() -> None:
    """Start the LSP server in stdio mode."""
    server = create_server()
    server.start_io()


# Default server instance for direct usage
server = create_server()
