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


def _build_click_signature(
    command: click.BaseCommand,
) -> list[ActionSignatureParameter]:
    """Extract signature parameters from a click command."""
    signature: list[ActionSignatureParameter] = []
    # Use getattr to work around type stub limitations
    params = getattr(command, "params", [])
    for param in params:
        if not isinstance(param, click.Option):
            continue
        if getattr(param, "hidden", False):
            continue

        entry: ActionSignatureParameter = {
            "name": (param.name or "").replace("-", "_"),
            "type": param.type.name
            if param.type.name
            else param.type.__class__.__name__,
            "description": param.help or "",
        }

        if not param.required:
            default_value = param.default
            # Skip callable defaults (lazy defaults)
            if not callable(default_value):
                entry["default"] = default_value

        if param.metavar is not None:
            entry["metavar"] = param.metavar

        if param.multiple:
            entry["multiple"] = str(param.multiple)

        if getattr(param, "is_flag", False):
            entry["is_bool_flag"] = True

        signature.append(entry)

    return signature


def build_command_hierarchy(root: RootCommand) -> CommandHierarchy:
    root_name = root.name or "qiime"
    root_node: JsonObject = {
        "name": root_name,
        "help": root.help,
        "short_help": root.short_help,
        "builtins": cast(list[JsonValue], sorted(root._builtin_commands.keys())),
    }

    for builtin_name, builtin_command in root._builtin_commands.items():
        builtin_properties: BuiltinCommandProperties = {
            "name": builtin_name,
            "help": builtin_command.help,
            "short_help": builtin_command.short_help,
            "type": "builtin",
        }
        # Check if builtin is a MultiCommand (has subcommands)
        if isinstance(builtin_command, click.MultiCommand):
            builtin_ctx = click.Context(builtin_command)
            builtin_node: JsonObject = cast(JsonObject, builtin_properties)
            for subcommand_name in builtin_command.list_commands(builtin_ctx):
                subcommand = builtin_command.get_command(builtin_ctx, subcommand_name)
                if subcommand is not None:
                    builtin_node[subcommand_name] = cast(
                        JsonObject,
                        {
                            "name": subcommand_name,
                            "help": subcommand.help,
                            "short_help": subcommand.short_help,
                            "type": "builtin_action",
                            "signature": _build_click_signature(subcommand),
                        },
                    )
            root_node[builtin_name] = builtin_node
        else:
            root_node[builtin_name] = cast(JsonObject, builtin_properties)

    ctx = click.Context(root)

    plugin_lookup = cast(Mapping[str, PluginCommandProperties], root._plugin_lookup)
    for plugin_name, plugin_data in plugin_lookup.items():
        plugin_command = _get_plugin_command(root, ctx, plugin_name)
        action_lookup: dict[str, ActionCommandProperties] = dict(
            plugin_command._action_lookup
        )
        action_lookup.update(getattr(plugin_command, "_hidden_actions", {}))

        plugin_node: JsonObject = cast(JsonObject, dict(plugin_data))
        for action_name, action_data in action_lookup.items():
            plugin_node[action_name] = cast(JsonObject, dict(action_data))
        root_node[plugin_name] = plugin_node

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
