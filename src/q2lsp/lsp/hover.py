"""Hover functionality for QIIME2 CLI commands.

Provides hover help text based on cursor position and catalog metadata.
"""

from __future__ import annotations

from collections.abc import Callable

from q2lsp.lsp.types import CompletionContext, TokenSpan
from q2lsp.qiime.catalog import QiimeCatalog


def get_hover_help(
    context: CompletionContext,
    *,
    get_help: Callable[[list[str]], str | None] | None = None,
    catalog: QiimeCatalog | None = None,
) -> str | None:
    """
    Get hover help text for the given completion context.

    Returns plain text string or None if no help is available.

    Args:
        context: Pre-resolved completion context from document analysis.
        get_help: Callback that takes command path and returns help text (preferred).
        catalog: Catalog metadata for hover help (preferred after get_help).

    Returns:
        Plain text string with help text, or None if no help is available.
    """
    # No hover if not in a qiime command
    if context.command is None:
        return None

    # Check if cursor is on a token
    if context.current_token is None:
        return None

    # Use help provider callback if available
    if get_help is not None:
        return _get_help_via_provider(
            context.command.tokens, context.token_index, get_help
        )

    if catalog is not None:
        return _get_help_via_catalog(
            context.command.tokens,
            context.current_token,
            context.token_index,
            catalog,
        )

    return None


def _get_help_via_provider(
    tokens: list[TokenSpan],
    token_index: int,
    get_help: Callable[[list[str]], str | None],
) -> str | None:
    """
    Get help text using the help provider callback.

    Args:
        tokens: List of command tokens.
        token_index: Index of the token being hovered.
        get_help: Callback that takes command path and returns help text.

    Returns:
        Help text string, or None if no help is available.
    """
    # Build command path based on token index
    if token_index == 0:
        # Hover on root ("qiime") - empty command path
        command_path: list[str] = []
    elif token_index == 1:
        # Hover on plugin/builtin - path is [plugin_name]
        command_path = [tokens[1].text]
    elif token_index == 2:
        # Hover on action - path is [plugin_name, action_name]
        if len(tokens) > 1:
            command_path = [tokens[1].text, tokens[2].text]
        else:
            return None
    else:
        # Hover on parameters or beyond - not implemented
        return None

    return get_help(command_path)


def _get_help_via_catalog(
    tokens: list[TokenSpan],
    current_token: TokenSpan,
    token_index: int,
    catalog: QiimeCatalog,
) -> str | None:
    if token_index == 0:
        return catalog.root_help()
    if token_index == 1:
        return catalog.command_help(current_token.text)
    if token_index == 2:
        plugin_name = tokens[1].text
        return catalog.action_help(plugin_name, current_token.text)
    return None
