from q2lsp.qiime.hierarchy_keys import (
    BUILTIN_NODE_METADATA_KEYS,
    COMMAND_METADATA_KEYS,
    ROOT_METADATA_KEYS,
)
from q2lsp.qiime.types import CommandHierarchy, JsonObject


def _get_root_node(hierarchy: CommandHierarchy) -> JsonObject | None:
    """Get the root node from hierarchy (usually 'qiime')."""
    if not hierarchy:
        return None
    return next(iter(hierarchy.values()), None)


def _get_valid_plugins_and_builtins(root_node: JsonObject) -> tuple[set[str], set[str]]:
    """Extract valid plugin and builtin names from root node."""
    # Get builtins
    builtins_data = root_node.get("builtins", [])
    valid_builtins = set()
    if isinstance(builtins_data, list):
        for name in builtins_data:
            if isinstance(name, str):
                valid_builtins.add(name)

    # Get plugins (keys that are not metadata)
    valid_plugins = set()
    for key, value in root_node.items():
        if not key:
            continue
        if key in ROOT_METADATA_KEYS:
            continue
        if key in valid_builtins:
            continue
        if not isinstance(value, dict):
            continue
        valid_plugins.add(key)

    return valid_plugins, valid_builtins


def _get_valid_actions(plugin_node: JsonObject) -> list[str]:
    """Extract valid action names from plugin node."""
    valid_actions = []
    for key, value in plugin_node.items():
        if not key:
            continue
        if key in COMMAND_METADATA_KEYS:
            continue
        if not isinstance(value, dict):
            continue
        valid_actions.append(key)

    return valid_actions


def _is_builtin_leaf(node: JsonObject) -> bool:
    """
    Check if a node is a builtin leaf (has no subcommands).

    Args:
        node: The plugin/builtin node to check.

    Returns:
        True if the node has no subcommands (leaf), False otherwise.
    """
    # If it's a builtin (type == "builtin"), check if it has subcommands
    if node.get("type") == "builtin":
        # A builtin is a leaf if it has no action/subcommand keys
        # Actions are keys that are not metadata
        for key, value in node.items():
            if key not in BUILTIN_NODE_METADATA_KEYS and isinstance(value, dict):
                return False
        return True
    return False
