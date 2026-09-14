from __future__ import annotations

import shlex
from typing import cast

import click
import pytest
from q2cli.commands import RootCommand

from q2lsp.core.diagnostics import collect_diagnostics
from q2lsp.core.diagnostics.codes import UNKNOWN_OPTION
from q2lsp.core.document import analyze_document
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.q2cli_gateway import build_qiime_hierarchy
from q2lsp.qiime.types import CommandHierarchy, JsonObject


@pytest.fixture(scope="module")
def hierarchy() -> CommandHierarchy:
    return build_qiime_hierarchy()


def test_build_qiime_hierarchy_root_properties(hierarchy: CommandHierarchy) -> None:
    root_name = "qiime"

    assert root_name in hierarchy
    root_entry = cast(JsonObject, hierarchy[root_name])
    assert root_entry["name"] == root_name
    assert isinstance(root_entry["help"], str | None)
    assert isinstance(root_entry["short_help"], str | None)
    assert isinstance(root_entry["builtins"], list)
    assert all(isinstance(name, str) for name in root_entry["builtins"])


def test_build_qiime_hierarchy_contains_plugin_action(
    hierarchy: CommandHierarchy,
) -> None:
    root_name = "qiime"
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

    assert isinstance(action_entry["id"], str)
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


def test_build_qiime_hierarchy_contains_tools_subcommands(
    hierarchy: CommandHierarchy,
) -> None:
    root_name = "qiime"
    root_entry = cast(JsonObject, hierarchy[root_name])

    assert "tools" in root_entry
    tools_entry = cast(JsonObject, root_entry["tools"])
    assert tools_entry["name"] == "tools"
    assert isinstance(tools_entry["help"], str | None)
    assert isinstance(tools_entry["short_help"], str | None)
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
    assert isinstance(action_entry["help"], str | None)
    assert isinstance(action_entry["short_help"], str | None)
    assert isinstance(action_entry["type"], str)
    assert action_entry["type"] == "builtin_action"
    assert isinstance(action_entry["signature"], list)

    signature = action_entry["signature"]
    for param in signature:
        assert isinstance(param, dict)
        assert isinstance(param["name"], str)
        assert isinstance(param["type"], str)
        assert isinstance(param["description"], str)


def test_build_qiime_hierarchy_builtin_details(hierarchy: CommandHierarchy) -> None:
    root_name = "qiime"
    root_entry = cast(JsonObject, hierarchy[root_name])

    assert isinstance(root_entry["builtins"], list)

    for builtin_name in root_entry["builtins"]:
        assert isinstance(builtin_name, str)
        assert builtin_name in root_entry
        builtin_entry = cast(JsonObject, root_entry[builtin_name])
        assert builtin_entry["name"] == builtin_name
        assert isinstance(builtin_entry["help"], str | None)
        assert isinstance(builtin_entry["short_help"], str | None)
        assert builtin_entry["type"] == "builtin"


@pytest.mark.parametrize(
    ("action_name", "arguments", "sdk_option"),
    [
        (
            "tabulate",
            ["--m-input-file", "metadata.tsv", "--o-visualization", "out.qzv"],
            "--p-input",
        ),
        (
            "distance-matrix",
            [
                "--m-metadata-file",
                "metadata.tsv",
                "--m-metadata-column",
                "group",
                "--o-distance-matrix",
                "out.qza",
            ],
            "--p-metadata",
        ),
    ],
)
def test_metadata_options_match_q2cli_parser(
    hierarchy: CommandHierarchy,
    action_name: str,
    arguments: list[str],
    sdk_option: str,
) -> None:
    root = RootCommand()
    root_ctx = click.Context(root)
    plugin = root.get_command(root_ctx, "metadata")
    assert isinstance(plugin, click.MultiCommand)
    plugin_ctx = click.Context(plugin, parent=root_ctx)
    action = plugin.get_command(plugin_ctx, action_name)
    assert isinstance(action, click.Command)

    # Parsing option names does not load files or invoke the QIIME action.
    parser = action.make_parser(click.Context(action, parent=plugin_ctx))
    _, remaining, _ = parser.parse_args(arguments.copy())
    assert remaining == []
    with pytest.raises(click.NoSuchOption):
        parser.parse_args([sdk_option, "metadata.tsv"])

    catalog = QiimeCatalog.from_hierarchy(hierarchy)
    source = f"qiime metadata {action_name} {shlex.join(arguments)}"
    assert collect_diagnostics(analyze_document(source), catalog) == []

    source += f" {sdk_option} metadata.tsv"
    issues = collect_diagnostics(analyze_document(source), catalog)
    assert [(issue.code, source[issue.start : issue.end]) for issue in issues] == [
        (UNKNOWN_OPTION, sdk_option)
    ]
