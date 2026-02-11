from __future__ import annotations

import json
from typing import Mapping, cast

import click
from q2cli.commands import PluginCommand, RootCommand

from q2lsp.qiime.types import (
    ActionCommandProperties,
    ActionSignatureParameter,
    BuiltinCommandProperties,
    CommandHierarchy,
    JsonObject,
    JsonValue,
    PluginCommandProperties,
)


def _normalize_param_name(name: str | None) -> str:
    """Normalize a parameter name by replacing hyphens with underscores."""
    return (name or "").replace("-", "_")


def _option_default(opt: click.Option) -> object | None:
    """Get the default value for an option, excluding callable defaults."""
    if opt.required:
        return None
    default_value = opt.default
    if callable(default_value):
        return None
    return default_value


def _option_type_name(opt: click.Option) -> str:
    """Get the type name for an option."""
    return getattr(opt.type, "name", "") or opt.type.__class__.__name__


def _click_option_to_signature_param(opt: click.Option) -> ActionSignatureParameter:
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
    command: click.BaseCommand,
) -> list[ActionSignatureParameter]:
    """Extract signature parameters from a click command."""
    signature: list[ActionSignatureParameter] = []
    params = getattr(command, "params", [])
    for param in params:
        if not isinstance(param, click.Option):
            continue
        if getattr(param, "hidden", False):
            continue
        signature.append(_click_option_to_signature_param(param))
    return signature


def _build_click_signature(
    command: click.BaseCommand,
) -> list[ActionSignatureParameter]:
    """Extract signature parameters from a click command."""
    return _extract_signature_from_click_command(command)


def _build_builtin_command_node(
    builtin_name: str, builtin_command: click.Command
) -> JsonObject:
    """Build a node for a builtin command, including its subcommands if any."""
    builtin_properties: BuiltinCommandProperties = {
        "name": builtin_name,
        "help": getattr(builtin_command, "help", None),
        "short_help": getattr(builtin_command, "short_help", None),
        "type": "builtin",
    }
    if isinstance(builtin_command, click.MultiCommand):
        builtin_ctx = click.Context(builtin_command)
        builtin_node: JsonObject = cast(JsonObject, builtin_properties)
        for subcommand_name in builtin_command.list_commands(builtin_ctx):
            subcommand = builtin_command.get_command(builtin_ctx, subcommand_name)
            if subcommand is None:
                continue
            if not isinstance(subcommand, click.Command):
                continue
            builtin_node[subcommand_name] = cast(
                JsonObject,
                {
                    "name": subcommand_name,
                    "help": getattr(subcommand, "help", None),
                    "short_help": getattr(subcommand, "short_help", None),
                    "type": "builtin_action",
                    "signature": _build_click_signature(subcommand),
                },
            )
        return builtin_node
    return cast(JsonObject, builtin_properties)


def _build_builtin_nodes(root: RootCommand) -> dict[str, JsonObject]:
    """Build all builtin command nodes."""
    nodes: dict[str, JsonObject] = {}
    for builtin_name, builtin_command in root._builtin_commands.items():
        nodes[builtin_name] = _build_builtin_command_node(builtin_name, builtin_command)
    return nodes


def _build_plugin_nodes(root: RootCommand, ctx: click.Context) -> dict[str, JsonObject]:
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


def build_command_hierarchy(root: RootCommand) -> CommandHierarchy:
    root_name = root.name or "qiime"
    root_node: JsonObject = {
        "name": root_name,
        "help": root.help,
        "short_help": root.short_help,
        "builtins": cast(list[JsonValue], sorted(root._builtin_commands.keys())),
    }

    # Add builtins
    for name, node in _build_builtin_nodes(root).items():
        root_node[name] = node

    # Add plugins
    ctx = click.Context(root)
    for name, node in _build_plugin_nodes(root, ctx).items():
        root_node[name] = node

    return {root_name: root_node}


def command_hierarchy_json(root: RootCommand, *, indent: int = 2) -> str:
    hierarchy = build_command_hierarchy(root)
    return json.dumps(hierarchy, ensure_ascii=False, indent=indent)


def _get_plugin_command(
    root: RootCommand, ctx: click.Context, plugin_name: str
) -> PluginCommand:
    command = root.get_command(ctx, plugin_name)
    if command is None:
        raise ValueError(f"Plugin command not found: {plugin_name}")
    if not isinstance(command, PluginCommand):
        raise TypeError(
            f"Unexpected command type for {plugin_name}: {type(command).__name__}"
        )
    return command
