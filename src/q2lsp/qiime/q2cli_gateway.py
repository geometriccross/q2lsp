"""Build QIIME hierarchy/catalog data from q2cli and create help providers."""

from __future__ import annotations

import re
import threading
from collections.abc import Callable, Mapping
from typing import cast

import click as _click
from q2cli.commands import PluginCommand as _PluginCommand
from q2cli.commands import RootCommand as _RootCommand
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.types import (
    ActionCommandProperties,
    ActionSignatureParameter,
    BuiltinCommandProperties,
    CommandHierarchy,
    JsonObject,
    JsonValue,
    PluginCommandProperties,
)

__all__ = [
    "build_qiime_catalog",
    "build_qiime_hierarchy",
    "create_qiime_help_provider",
]


def _normalize_param_name(name: str | None) -> str:
    """Normalize a parameter name by replacing hyphens with underscores."""
    return (name or "").replace("-", "_")


def _option_default(opt: _click.Option) -> object | None:
    """Get the default value for an option, excluding callable defaults."""
    if opt.required:
        return None
    default_value = opt.default
    if callable(default_value):
        return None
    return default_value


def _option_type_name(opt: _click.Option) -> str:
    """Get the type name for an option."""
    return getattr(opt.type, "name", "") or opt.type.__class__.__name__


def _click_option_to_signature_param(opt: _click.Option) -> ActionSignatureParameter:
    """Convert a click Option to an ActionSignatureParameter dict."""
    entry: ActionSignatureParameter = {
        "name": _normalize_param_name(opt.name),
        "type": _option_type_name(opt),
        "description": opt.help or "",
    }

    default_value = _option_default(opt)
    if default_value is not None:
        entry["default"] = cast(JsonValue, default_value)

    if opt.required:
        entry["required"] = True

    if opt.metavar is not None:
        entry["metavar"] = opt.metavar

    if opt.multiple:
        entry["multiple"] = str(opt.multiple)

    flag_value = getattr(opt, "flag_value", None)
    bool_flag = (getattr(opt, "is_flag", False) and isinstance(flag_value, bool)) or (
        getattr(opt, "secondary_opts", []) and isinstance(flag_value, bool)
    )
    if bool_flag:
        entry["is_bool_flag"] = True

    return entry


def _extract_signature_from_click_command(
    command: _click.BaseCommand,
) -> list[ActionSignatureParameter]:
    """Extract signature parameters from a click command."""
    signature: list[ActionSignatureParameter] = []
    params = getattr(command, "params", [])
    for param in params:
        if not isinstance(param, _click.Option):
            continue
        if getattr(param, "hidden", False):
            continue
        signature.append(_click_option_to_signature_param(param))
    return signature


def _build_builtin_command_node(
    builtin_name: str, builtin_command: _click.Command
) -> JsonObject:
    """Build a node for a builtin command, including its subcommands if any."""
    builtin_properties: BuiltinCommandProperties = {
        "name": builtin_name,
        "help": getattr(builtin_command, "help", None),
        "short_help": getattr(builtin_command, "short_help", None),
        "type": "builtin",
    }
    if isinstance(builtin_command, _click.MultiCommand):
        builtin_ctx = _click.Context(builtin_command)
        builtin_node: JsonObject = cast(JsonObject, builtin_properties)
        for subcommand_name in builtin_command.list_commands(builtin_ctx):
            subcommand = builtin_command.get_command(builtin_ctx, subcommand_name)
            if subcommand is None:
                continue
            if not isinstance(subcommand, _click.Command):
                continue
            subcommand_properties: BuiltinCommandProperties = {
                "name": subcommand_name,
                "help": getattr(subcommand, "help", None),
                "short_help": getattr(subcommand, "short_help", None),
                "type": "builtin_action",
                "signature": _extract_signature_from_click_command(subcommand),
            }
            builtin_node[subcommand_name] = cast(JsonObject, subcommand_properties)
        return builtin_node
    return cast(JsonObject, builtin_properties)


def _build_builtin_nodes(root: _RootCommand) -> dict[str, JsonObject]:
    """Build all builtin command nodes."""
    nodes: dict[str, JsonObject] = {}
    for builtin_name, builtin_command in root._builtin_commands.items():
        nodes[builtin_name] = _build_builtin_command_node(builtin_name, builtin_command)
    return nodes


def _build_plugin_nodes(root: _RootCommand, ctx: _click.Context) -> dict[str, JsonObject]:
    """Build all plugin command nodes."""
    plugin_lookup = cast(Mapping[str, PluginCommandProperties], root._plugin_lookup)
    nodes: dict[str, JsonObject] = {}
    for plugin_name, plugin_data in plugin_lookup.items():
        plugin_command = _get_plugin_command(root, ctx, plugin_name)
        action_lookup: dict[str, ActionCommandProperties] = dict(
            plugin_command._action_lookup
        )
        action_lookup.update(getattr(plugin_command, "_hidden_actions", {}))
        plugin_node: JsonObject = cast(JsonObject, dict(plugin_data))
        for action_name, action_data in action_lookup.items():
            plugin_node[action_name] = cast(JsonObject, dict(action_data))
        nodes[plugin_name] = plugin_node
    return nodes


def _build_command_hierarchy_from_root(root: _RootCommand) -> CommandHierarchy:
    root_name = root.name or "qiime"
    root_node: JsonObject = {
        "name": root_name,
        "help": root.help,
        "short_help": root.short_help,
        "builtins": cast(list[JsonValue], sorted(root._builtin_commands.keys())),
    }

    for name, node in _build_builtin_nodes(root).items():
        root_node[name] = node

    ctx = _click.Context(root)
    for name, node in _build_plugin_nodes(root, ctx).items():
        root_node[name] = node

    return {root_name: root_node}


def build_qiime_hierarchy() -> CommandHierarchy:
    """Build the QIIME command hierarchy without exposing q2cli types."""
    return _build_command_hierarchy_from_root(_RootCommand())


def build_qiime_catalog() -> QiimeCatalog:
    """Build the minimal owned QIIME catalog abstraction."""
    return QiimeCatalog.from_hierarchy(build_qiime_hierarchy())


def _get_plugin_command(
    root: _RootCommand, ctx: _click.Context, plugin_name: str
) -> _PluginCommand:
    command = root.get_command(ctx, plugin_name)
    if command is None:
        raise ValueError(f"Plugin command not found: {plugin_name}")
    if not isinstance(command, _PluginCommand):
        raise TypeError(
            f"Unexpected command type for {plugin_name}: {type(command).__name__}"
        )
    return command


def _sanitize_help_text(text: str) -> str:
    """
    Sanitize help text by removing control characters and ANSI escape sequences.

    Removes:
    - ANSI escape sequences (e.g., \\x1b[31m, \\x1b[0m)
    - ASCII control characters except \\n and \\t
    - \\r characters (and normalizes CRLF to LF)

    Preserves:
    - Newlines (\\n)
    - Tabs (\\t)
    - Indentation

    Args:
        text: Raw help text from command.get_help()

    Returns:
        Sanitized help text safe for LSP hover display.
    """
    # Remove CSI escape sequences such as colors, line clears, cursor moves,
    # and private-mode toggles.
    ansi_pattern = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
    text = ansi_pattern.sub("", text)

    # Remove CRLF (normalize to LF)
    text = text.replace("\r\n", "\n")

    # Remove any remaining \r characters
    text = text.replace("\r", "")

    # Remove all ASCII control characters except \n and \t
    # Control chars are in range 0x00-0x1F, plus 0x7F (DEL)
    # We want to keep 0x0A (\n) and 0x09 (\t)
    result = []
    for char in text:
        code = ord(char)
        if (code < 32 and code not in (9, 10)) or code == 127:
            continue
        result.append(char)
    return "".join(result)


# Singleton root command instance for lazy loading
_cached_root_command: _RootCommand | None = None
_root_command_lock = threading.Lock()


def _get_root_command() -> _RootCommand:
    """Get or create the cached RootCommand instance (thread-safe)."""
    global _cached_root_command
    if _cached_root_command is None:
        with _root_command_lock:
            # Double-check pattern
            if _cached_root_command is None:
                _cached_root_command = _RootCommand()
    return _cached_root_command


def create_qiime_help_provider(
    *, max_content_width: int = 80, color: bool = False
) -> Callable[[list[str]], str | None]:
    """
    Create a help provider function for QIIME2 commands.

    The returned function uses click.Context to generate help text that
    matches the CLI output of `qiime ... --help`.

    Args:
        max_content_width: Maximum line width for help text (default: 80).
        color: Whether to include ANSI color codes (default: False).

    Returns:
        A callable that takes a command path and returns help text, or None.
    """

    def _get_help(command_path: list[str]) -> str | None:
        """Get help text for the given command path."""
        root = _get_root_command()
        # Build context chain with parent references for correct Usage lines
        ctx = _click.Context(
            root,
            max_content_width=max_content_width,
            color=color,
            info_name="qiime",
        )

        # Navigate to the command
        cmd: _click.Command = root
        for name in command_path:
            if isinstance(cmd, _click.MultiCommand):
                subcommand = cmd.get_command(ctx, name)
                if subcommand is None:
                    return None
                cmd = subcommand
                # Create new context with parent reference for proper command path
                ctx = _click.Context(
                    cmd,
                    parent=ctx,
                    max_content_width=max_content_width,
                    color=color,
                    info_name=name,
                )
            else:
                return None

        # Generate and return help text (sanitized)
        help_text = cmd.get_help(ctx)
        return _sanitize_help_text(help_text)

    return _get_help
