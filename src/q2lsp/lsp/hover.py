"""Hover functionality for QIIME2 CLI commands.

Provides hover help text based on cursor position and command hierarchy.
"""

from __future__ import annotations

from typing import Callable

from q2lsp.lsp.completion_context import get_completion_context
from q2lsp.lsp.types import TokenSpan
from q2lsp.qiime.types import CommandHierarchy, JsonObject


def get_hover_help(
    text: str,
    offset: int,
    *,
    hierarchy: CommandHierarchy | None = None,
    get_help: Callable[[list[str]], str | None] | None = None,
) -> str | None:
    """
    Get hover help text at the given cursor position.

    Returns plain text string or None if no help is available.

    Args:
        text: The full document text.
        offset: Cursor position (0-based offset in original text).
        hierarchy: The QIIME2 command hierarchy (legacy, optional).
        get_help: Callback that takes command path and returns help text (preferred).

    Returns:
        Plain text string with help text, or None if no help is available.
    """
    # Get completion context to understand where we are in the command
    ctx = get_completion_context(text, offset)

    # No hover if not in a qiime command
    if ctx.command is None:
        return None

    # Check if cursor is on a token
    if ctx.current_token is None:
        return None

    # Use help provider callback if available
    if get_help is not None:
        return _get_help_via_provider(ctx.command.tokens, ctx.token_index, get_help)

    # Legacy behavior: use hierarchy
    if hierarchy is None:
        return None

    # Determine what to show based on token index
    token_index = ctx.token_index

    if token_index == 0:
        # Hover on "qiime" - show root help
        return _get_root_help(hierarchy)
    elif token_index == 1:
        # Hover on plugin/builtin name - show plugin help
        plugin_name = ctx.current_token.text
        return _get_plugin_help(hierarchy, plugin_name)
    elif token_index == 2:
        # Hover on action name - show action help
        plugin_name = ctx.command.tokens[1].text if len(ctx.command.tokens) > 1 else ""
        action_name = ctx.current_token.text
        return _get_action_help(hierarchy, plugin_name, action_name)
    else:
        # Hover on parameters or beyond - not implemented
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


def _get_root_node(hierarchy: CommandHierarchy) -> JsonObject | None:
    """Get the root node from hierarchy (usually 'qiime')."""
    if not hierarchy:
        return None
    return next(iter(hierarchy.values()), None)


def _get_root_help(hierarchy: CommandHierarchy) -> str | None:
    """
    Get root level help text.

    Args:
        hierarchy: The QIIME2 command hierarchy.

    Returns:
        Help text for root command, or None if not available.
    """
    root_node = _get_root_node(hierarchy)
    if root_node is None:
        return None

    # Prefer help, fallback to short_help
    help_text = root_node.get("help") or root_node.get("short_help")
    if not isinstance(help_text, str):
        return None

    return help_text


def _get_plugin_help(hierarchy: CommandHierarchy, plugin_name: str) -> str | None:
    """
    Get plugin level help text.

    Args:
        hierarchy: The QIIME2 command hierarchy.
        plugin_name: Name of the plugin/builtin.

    Returns:
        Help text for plugin, or None if not available.
    """
    root_node = _get_root_node(hierarchy)
    if root_node is None:
        return None

    plugin_node = root_node.get(plugin_name)
    if not isinstance(plugin_node, dict):
        return None

    # For builtins, prefer help/short_help if present
    # For plugins, prefer short_description, fallback to description
    help_text = (
        plugin_node.get("help")
        or plugin_node.get("short_help")
        or plugin_node.get("short_description")
        or plugin_node.get("description")
    )

    if not isinstance(help_text, str):
        return None

    return help_text


def _get_action_help(
    hierarchy: CommandHierarchy, plugin_name: str, action_name: str
) -> str | None:
    """
    Get action level help text.

    Args:
        hierarchy: The QIIME2 command hierarchy.
        plugin_name: Name of the plugin.
        action_name: Name of the action.

    Returns:
        Help text for action, or None if not available.
    """
    root_node = _get_root_node(hierarchy)
    if root_node is None:
        return None

    plugin_node = root_node.get(plugin_name)
    if not isinstance(plugin_node, dict):
        return None

    action_node = plugin_node.get(action_name)
    if not isinstance(action_node, dict):
        return None

    # Get action description
    description = action_node.get("description")
    if not isinstance(description, str) or not description:
        return None

    help_text = description

    # Append epilog lines if present
    epilog = action_node.get("epilog")
    if isinstance(epilog, list) and epilog:
        epilog_text = "\n".join(str(line) for line in epilog)
        if epilog_text:
            help_text = f"{help_text}\n\n{epilog_text}"

    return help_text
