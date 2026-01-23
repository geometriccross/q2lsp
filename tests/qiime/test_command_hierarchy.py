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

    # Explicitly assert that at least one action exists
    assert action_lookup, "action_lookup should not be empty"

    action_name, action_data = next(iter(action_lookup.items()))
    assert action_name in plugin_entry
    action_entry = cast(JsonObject, plugin_entry[action_name])
    assert action_entry["id"] == action_data["id"]

    # Verify action entry has required ActionCommandProperties fields
    assert "name" in action_entry
    assert isinstance(action_entry["name"], str)
    assert "type" in action_entry
    assert "description" in action_entry
    assert "signature" in action_entry
    assert isinstance(action_entry["signature"], list)
    assert "epilog" in action_entry
    assert "deprecated" in action_entry
    assert "migrated" in action_entry


def test_build_command_hierarchy_contains_tools_subcommands() -> None:
    root = RootCommand()
    hierarchy = build_command_hierarchy(root)
    root_name = root.name or "qiime"
    root_entry = cast(JsonObject, hierarchy[root_name])

    # Get the tools entry from the hierarchy
    assert "tools" in root_entry
    tools_entry = cast(JsonObject, root_entry["tools"])

    # Verify tools has type "builtin"
    assert tools_entry["type"] == "builtin"

    # Expected subcommands for qiime tools
    expected_tools_subcommands = [
        "import",
        "export",
        "peek",
        "validate",
        "view",
        "extract",
        "citations",
        "list-types",
        "list-formats",
        "cast-metadata",
        "inspect-metadata",
        "cache-create",
        "cache-store",
        "cache-fetch",
        "cache-remove",
        "cache-status",
        "cache-import",
        "cache-export",
        "cache-garbage-collection",
        "replay-provenance",
        "replay-citations",
        "replay-supplement",
        "make-report",
        "annotation-create",
        "annotation-fetch",
        "annotation-list",
        "annotation-remove",
        "signature-verify",
    ]

    # Verify all expected subcommands exist
    for subcommand_name in expected_tools_subcommands:
        assert subcommand_name in tools_entry, f"Missing subcommand: {subcommand_name}"

    # For the import subcommand, verify it has the expected structure
    import_entry = cast(JsonObject, tools_entry["import"])
    assert import_entry["name"] == "import"
    assert import_entry["type"] == "builtin_action"
    assert "help" in import_entry
    assert "short_help" in import_entry
    assert "signature" in import_entry
    assert isinstance(import_entry["signature"], list)
    names = {
        str(param["name"])
        for param in import_entry["signature"]
        if isinstance(param, dict) and "name" in param
    }
    assert "input_path" in names
    assert "output_path" in names


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
