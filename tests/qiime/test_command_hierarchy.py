from __future__ import annotations

import json
from typing import cast

import click
from q2cli.commands import RootCommand

from q2lsp.qiime.command_hierarchy import (
    build_command_hierarchy,
    command_hierarchy_json,
)
from q2lsp.qiime.types import JsonObject


def test_build_command_hierarchy_root_properties() -> None:
    root = RootCommand()
    hierarchy = build_command_hierarchy(root)
    root_name = root.name or "qiime"

    assert root_name in hierarchy
    root_entry = cast(JsonObject, hierarchy[root_name])
    assert root_entry["name"] == root_name
    assert isinstance(root_entry["builtins"], list)


def test_build_command_hierarchy_contains_plugin_action() -> None:
    root = RootCommand()
    hierarchy = build_command_hierarchy(root)
    root_name = root.name or "qiime"
    root_entry = cast(JsonObject, hierarchy[root_name])

    plugin_name, plugin_data = next(iter(root._plugin_lookup.items()))
    assert plugin_name in root_entry
    plugin_entry = cast(JsonObject, root_entry[plugin_name])
    assert plugin_entry["id"] == plugin_data["id"]

    ctx = click.Context(root)
    plugin_command = root.get_command(ctx, plugin_name)
    assert plugin_command is not None

    action_lookup = dict(plugin_command._action_lookup)
    action_lookup.update(getattr(plugin_command, "_hidden_actions", {}))
    action_name, action_data = next(iter(action_lookup.items()))
    assert action_name in plugin_entry
    action_entry = cast(JsonObject, plugin_entry[action_name])
    assert action_entry["id"] == action_data["id"]


def test_build_command_hierarchy_builtin_details() -> None:
    root = RootCommand()
    hierarchy = build_command_hierarchy(root)
    root_name = root.name or "qiime"
    root_entry = cast(JsonObject, hierarchy[root_name])

    # Assert that builtins list exists (existing assertion)
    assert isinstance(root_entry["builtins"], list)

    # For each builtin command, assert the hierarchy has the required metadata
    for builtin_name in root._builtin_commands.keys():
        assert builtin_name in root_entry
        builtin_entry = cast(JsonObject, root_entry[builtin_name])
        assert builtin_entry["name"] == builtin_name
        assert "help" in builtin_entry
        assert "short_help" in builtin_entry
        assert builtin_entry["type"] == "builtin"


def test_command_hierarchy_json_roundtrip() -> None:
    root = RootCommand()
    payload = command_hierarchy_json(root)
    data = json.loads(payload)
    root_name = root.name or "qiime"
    assert root_name in data
