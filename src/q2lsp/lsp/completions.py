"""Completion logic for QIIME2 CLI commands.

Routes completion requests based on CompletionContext mode and
generates completion items from the CommandHierarchy.
"""

from __future__ import annotations

from typing import NamedTuple

from q2lsp.lsp.types import CompletionContext, CompletionKind, CompletionMode
from q2lsp.qiime.options import (
    format_qiime_option_label,
    option_label_matches_prefix,
    qiime_option_prefix,
)
from q2lsp.qiime.types import CommandHierarchy, JsonObject

# Metadata keys to skip when looking for commands/actions
_ROOT_METADATA_KEYS = frozenset({"name", "help", "short_help", "builtins"})

_COMMAND_METADATA_KEYS = frozenset(
    {
        "id",
        "name",
        "version",
        "website",
        "user_support_text",
        "description",
        "short_description",
        "short_help",
        "help",
        "actions",
        "type",
    }
)


class CompletionItem(NamedTuple):
    """A completion suggestion."""

    label: str  # Display text
    detail: str  # Additional info (e.g., description)
    kind: CompletionKind  # "plugin", "action", "parameter", "builtin"
    insert_text: str | None = None  # Text to insert (if different from label)


def get_completions(
    ctx: CompletionContext,
    hierarchy: CommandHierarchy,
) -> list[CompletionItem]:
    """
    Get completion items based on the completion context.

    Routes to appropriate handler based on mode:
    - "root": Complete plugin names and builtin commands
    - "plugin": Complete action names within a plugin
    - "parameter": Complete parameter names for an action
    - "none": Return empty list

    Args:
        ctx: The completion context from the parser
        hierarchy: The QIIME2 command hierarchy

    Returns:
        List of CompletionItem matching the prefix
    """
    if ctx.mode == CompletionMode.NONE or ctx.command is None:
        return []

    # Get the root node (usually "qiime")
    root_node = _get_root_node(hierarchy)
    if root_node is None:
        return []

    prefix = ctx.prefix

    if ctx.mode == CompletionMode.ROOT:
        return _complete_root(root_node, prefix)
    elif ctx.mode == CompletionMode.PLUGIN:
        # Get plugin name from token 1
        plugin_name = _get_token_text(ctx, 1)
        return _complete_plugin(root_node, plugin_name, prefix)
    elif ctx.mode == CompletionMode.PARAMETER:
        # Get plugin name from token 1, action name from token 2
        plugin_name = _get_token_text(ctx, 1)
        action_name = _get_token_text(ctx, 2)
        # Get already used parameters
        used_params = _get_used_parameters(ctx)
        return _complete_parameters(
            root_node, plugin_name, action_name, prefix, used_params
        )

    return []


def _get_root_node(hierarchy: CommandHierarchy) -> JsonObject | None:
    """Get the root node from hierarchy (usually 'qiime')."""
    if not hierarchy:
        return None
    # Return the first (and usually only) root
    return next(iter(hierarchy.values()), None)


def _get_token_text(ctx: CompletionContext, index: int) -> str:
    """Get token text at index, or empty string if not available."""
    if ctx.command is None or index >= len(ctx.command.tokens):
        return ""
    return ctx.command.tokens[index].text


def _get_used_parameters(ctx: CompletionContext) -> set[str]:
    """Get set of parameter names already used in the command."""
    used: set[str] = set()
    if ctx.command is None:
        return used

    # Parameters start at token index 3
    for token in ctx.command.tokens[3:]:
        text = token.text
        if text.startswith("--"):
            # Strip leading dashes and any value after =
            param = text.lstrip("-").split("=")[0].replace("-", "_")
            used.add(param)

            # Normalize prefixed options: add base name for prefixed params
            # If param matches pattern <prefix>_<rest> where prefix in {"i","o","p","m"}
            parts = param.split("_", 1)
            if len(parts) == 2 and parts[0] in {"i", "o", "p", "m"}:
                base_name = parts[1]
                used.add(base_name)

    return used


def _option_matches_prefix(option_name: str, prefix_filter: str) -> bool:
    """Wrapper for option_label_matches_prefix to keep exported name for tests."""
    return option_label_matches_prefix(option_name, prefix_filter)


def _complete_root(root_node: JsonObject, prefix: str) -> list[CompletionItem]:
    """
    Complete plugin names and builtin commands at root level.

    Root node contains:
    - "builtins": list of builtin command names
    - Other keys: plugin names (excluding "name", "help", "short_help")
    """
    items: list[CompletionItem] = []

    # Get builtin commands
    builtins = root_node.get("builtins", [])
    if isinstance(builtins, list):
        for name in builtins:
            if isinstance(name, str) and name.startswith(prefix):
                # Get builtin details
                builtin_data = root_node.get(name, {})
                detail = ""
                if isinstance(builtin_data, dict):
                    detail = str(builtin_data.get("short_help", "")) or str(
                        builtin_data.get("help", "")
                    )
                items.append(
                    CompletionItem(
                        label=name,
                        detail=detail or "Built-in command",
                        kind=CompletionKind.BUILTIN,
                    )
                )

    # Get plugin names (keys that are not metadata)
    for key, value in root_node.items():
        if not key:  # Skip empty keys
            continue
        if key in _ROOT_METADATA_KEYS:
            continue
        if key in (builtins if isinstance(builtins, list) else []):
            continue  # Already added as builtin
        if not key.startswith(prefix):
            continue
        if not isinstance(value, dict):
            continue

        # It's a plugin
        detail = str(value.get("short_description", "")) or str(
            value.get("description", "")
        )
        items.append(
            CompletionItem(
                label=key,
                detail=detail or "Plugin",
                kind=CompletionKind.PLUGIN,
            )
        )

    return items


def _complete_plugin(
    root_node: JsonObject,
    plugin_name: str,
    prefix: str,
) -> list[CompletionItem]:
    """
    Complete action names within a plugin or builtin command.

    Plugin/builtin node contains:
    - Metadata: "id", "name", "version", "website", "type", "short_help", etc.
    - Action keys: action names with their properties

    Note: Actions are expected as direct keys under the command node,
    not nested in an "actions" array. The "actions" key in metadata_keys
    is included to skip any summary metadata that might use this name.
    """
    items: list[CompletionItem] = []

    # Get builtin list for reference
    builtins = root_node.get("builtins", [])
    is_builtin = isinstance(builtins, list) and plugin_name in builtins

    # Get the command node (works for both plugins and builtins)
    command_node = root_node.get(plugin_name)
    if not isinstance(command_node, dict):
        return items

    # Look for actions in the command node
    for key, value in command_node.items():
        if not key:  # Skip empty keys
            continue
        if key in _COMMAND_METADATA_KEYS:
            continue
        if not key.startswith(prefix):
            continue
        if not isinstance(value, dict):
            continue

        # It's an action
        detail = str(value.get("description", ""))
        items.append(
            CompletionItem(
                label=key,
                detail=detail or "Action",
                kind=CompletionKind.ACTION,
            )
        )

    # If no actions found and it's a builtin, return help option
    if not items and is_builtin:
        return _complete_builtin_options(prefix)

    return items


def _complete_builtin_options(prefix: str) -> list[CompletionItem]:
    """Return common options for builtin commands."""
    options = [
        ("--help", "Show help message"),
    ]
    items: list[CompletionItem] = []
    for opt, desc in options:
        if opt.startswith(prefix):
            items.append(
                CompletionItem(
                    label=opt,
                    detail=desc,
                    kind=CompletionKind.PARAMETER,
                )
            )
    return items


def _complete_parameters(
    root_node: JsonObject,
    plugin_name: str,
    action_name: str,
    prefix: str,
    used_params: set[str],
) -> list[CompletionItem]:
    """
    Complete parameter names for an action.

    Action node contains:
    - "signature": list of parameter definitions
    """
    items: list[CompletionItem] = []

    # Preserve the incoming prefix filter to avoid shadowing
    prefix_filter = prefix

    # Check if it's a builtin command
    builtins = root_node.get("builtins", [])
    is_builtin = isinstance(builtins, list) and plugin_name in builtins

    # Get plugin node
    plugin_node = root_node.get(plugin_name)
    if not isinstance(plugin_node, dict):
        return items

    # Get action node
    action_node = plugin_node.get(action_name)
    if not isinstance(action_node, dict):
        return items

    # Get signature (list of parameters)
    signature = action_node.get("signature", [])
    if not isinstance(signature, list):
        if is_builtin:
            return _complete_builtin_options(prefix_filter)
        return items

    if not signature:
        if is_builtin:
            return _complete_builtin_options(prefix_filter)
        return items

    for param in signature:
        if not isinstance(param, dict):
            continue

        name = param.get("name", "")
        if not isinstance(name, str) or not name:
            continue

        # Skip already used parameters
        if name in used_params:
            continue

        # Derive prefix and format option name
        option_prefix = qiime_option_prefix(param)
        option_name = format_qiime_option_label(option_prefix, name)
        if not _option_matches_prefix(option_name, prefix_filter):
            continue

        # Build detail string
        detail_parts: list[str] = []
        param_type = param.get("type", "")
        if param_type:
            detail_parts.append(f"[{param_type}]")
        description = param.get("description", "")
        if description:
            detail_parts.append(str(description))

        # Check if required (no default)
        is_required = "default" not in param
        if is_required:
            detail_parts.insert(0, "(required)")

        items.append(
            CompletionItem(
                label=option_name,
                detail=" ".join(detail_parts) if detail_parts else "Parameter",
                kind=CompletionKind.PARAMETER,
            )
        )

    # Always add --help
    if "--help".startswith(prefix_filter) and "help" not in used_params:
        items.append(
            CompletionItem(
                label="--help",
                detail="Show help message",
                kind=CompletionKind.PARAMETER,
            )
        )

    return items
