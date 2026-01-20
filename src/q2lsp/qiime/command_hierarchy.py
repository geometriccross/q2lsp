from __future__ import annotations

import json
from typing import Mapping, cast

import click
from q2cli.commands import PluginCommand, RootCommand

from q2lsp.qiime.types import (
    ActionCommandProperties,
    CommandHierarchy,
    JsonObject,
    JsonValue,
    PluginCommandProperties,
)


def build_command_hierarchy(root: RootCommand) -> CommandHierarchy:
    root_name = root.name or "qiime"
    root_node: JsonObject = {
        "name": root_name,
        "help": root.help,
        "short_help": root.short_help,
        "builtins": cast(list[JsonValue], sorted(root._builtin_commands.keys())),
    }
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
