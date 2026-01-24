from __future__ import annotations

import json
from typing import cast

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

    builtin_names = set(root_entry.get("builtins", [])) | {
        root_name,
        "builtins",
    }

    plugin_entry = None
    for key, value in root_entry.items():
        if key in builtin_names:
            continue
        if isinstance(value, dict) and "id" in value and "name" in value:
            plugin_entry = cast(JsonObject, value)
            break

    assert plugin_entry is not None, "No plugin entry found in hierarchy"

    metadata_keys = {"id", "name", "description", "short_description"}

    action_entry = None
    for key, value in plugin_entry.items():
        if key in metadata_keys:
            continue
        if (
            isinstance(value, dict)
            and "id" in value
            and isinstance(value.get("signature"), list)
        ):
            action_entry = cast(JsonObject, value)
            break

    assert action_entry is not None, "No action entry found in plugin"

    assert isinstance(action_entry["name"], str)
    assert isinstance(action_entry["type"], str)
    assert isinstance(action_entry["description"], str)
    assert isinstance(action_entry["signature"], list)
    assert isinstance(action_entry["epilog"], list)
    assert isinstance(action_entry["deprecated"], bool)
    assert isinstance(action_entry["migrated"], (bool, dict))

    signature = action_entry["signature"]
    for param in signature:
        assert isinstance(param, dict)
        assert isinstance(param["name"], str)
        assert isinstance(param["type"], str)


def test_build_command_hierarchy_contains_tools_subcommands() -> None:
    root = RootCommand()
    hierarchy = build_command_hierarchy(root)
    root_name = root.name or "qiime"
    root_entry = cast(JsonObject, hierarchy[root_name])

    assert "tools" in root_entry
    tools_entry = cast(JsonObject, root_entry["tools"])
    assert tools_entry["type"] == "builtin"

    expected_subset = {"import", "export", "peek", "validate"}
    available_tools = {
        name for name, value in tools_entry.items() if isinstance(value, dict)
    }
    assert expected_subset <= available_tools

    action_name = (
        "import" if "import" in available_tools else next(iter(available_tools))
    )
    action_entry = cast(JsonObject, tools_entry[action_name])

    assert isinstance(action_entry["name"], str)
    assert isinstance(action_entry["type"], str)
    assert action_entry["type"] == "builtin_action"
    assert isinstance(action_entry["signature"], list)

    signature = action_entry["signature"]
    for param in signature:
        assert isinstance(param, dict)
        assert isinstance(param["name"], str)
        assert isinstance(param["type"], str)


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
