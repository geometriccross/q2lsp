"""Tests for completion adapter."""

from __future__ import annotations

import importlib

from q2lsp.adapters.completion_adapter import (
    get_used_parameters,
    to_completion_data,
    to_completion_query,
)
from q2lsp.core.types import CompletionKind, CompletionMode
from q2lsp.qiime.catalog import QiimeCatalog


def test_maps_boundary_values_to_core_query() -> None:
    query = to_completion_query(
        mode="parameter",
        prefix="--",
        command_tokens=("qiime", "feature-table", "summarize", "--"),
    )

    assert query.mode == CompletionMode.PARAMETER
    assert query.prefix == "--"
    assert query.normalized_prefix == ""
    assert query.plugin_name == "feature-table"
    assert query.action_name == "summarize"
    assert query.used_parameters == frozenset()


def test_unknown_mode_maps_to_none() -> None:
    query = to_completion_query(mode="unknown", prefix="", command_tokens=())

    assert query.mode == CompletionMode.NONE
    assert query.plugin_name == ""
    assert query.action_name == ""


def test_maps_root_plugin_and_parameter_modes_with_tokens() -> None:
    root_query = to_completion_query(
        mode="root",
        prefix="fe",
        command_tokens=("qiime", "fe"),
    )
    plugin_query = to_completion_query(
        mode="plugin",
        prefix="su",
        command_tokens=("qiime", "feature-table", "su"),
    )
    parameter_query = to_completion_query(
        mode="parameter",
        prefix="--p-s",
        command_tokens=(
            "qiime",
            "feature-table",
            "summarize",
            "--i-table=table.qza",
            "--p-sampling-depth",
        ),
    )

    assert root_query.mode == CompletionMode.ROOT
    assert root_query.normalized_prefix == "fe"
    assert root_query.plugin_name == "fe"
    assert root_query.action_name == ""

    assert plugin_query.mode == CompletionMode.PLUGIN
    assert plugin_query.plugin_name == "feature-table"
    assert plugin_query.action_name == "su"

    assert parameter_query.mode == CompletionMode.PARAMETER
    assert parameter_query.normalized_prefix == "p-s"
    assert parameter_query.plugin_name == "feature-table"
    assert parameter_query.action_name == "summarize"
    assert parameter_query.used_parameters == frozenset({"table", "sampling_depth"})


def test_empty_tokens_maps_to_none_mode() -> None:
    query = to_completion_query(mode="root", prefix="", command_tokens=())

    assert query.mode == CompletionMode.NONE


def test_get_used_parameters_ignores_empty_option_stub() -> None:
    used = get_used_parameters(
        ("qiime", "feature-table", "summarize", "--", "--i-table", "x")
    )

    assert used == {"table"}


def test_get_used_parameters_normalizes_qiime_options() -> None:
    used = get_used_parameters(
        (
            "qiime",
            "feature-table",
            "summarize",
            "--i-table=table.qza",
            "--o-visualization",
            "viz.qzv",
            "--p-sampling-depth",
            "1000",
            "--m-metadata-file=metadata.tsv",
            "--help",
            "--i-table=other.qza",
        )
    )

    assert used == {
        "table",
        "visualization",
        "sampling_depth",
        "metadata_file",
        "help",
    }


def test_normalizes_catalog_to_core_data() -> None:
    catalog = QiimeCatalog.from_hierarchy(
        {
            "qiime": {
                "builtins": ["info"],
                "info": {"short_help": "Display information"},
                "feature-table": {
                    "short_description": "Feature table operations",
                    "summarize": {
                        "description": "Summarize feature table",
                        "signature": [
                            {
                                "name": "table",
                                "type": "FeatureTable",
                                "description": "Input table",
                                "signature_type": "input",
                            }
                        ],
                    },
                },
            }
        }
    )

    data = to_completion_data(catalog)

    assert {item.label for item in data.root_items} == {"info", "feature-table"}
    command = next(command for command in data.commands if command.name == "feature-table")
    assert command.is_builtin is False
    assert command.actions[0].item.label == "summarize"
    assert command.actions[0].parameters[0].item.label == "--i-table"


def test_normalizes_signature_kinds_and_required_details() -> None:
    catalog = QiimeCatalog.from_hierarchy(
        {
            "qiime": {
                "feature-table": {
                    "summarize": {
                        "description": "Summarize feature table",
                        "signature": [
                            {
                                "name": "visualization",
                                "type": "Visualization",
                                "description": "Output visualization",
                                "signature_type": "output",
                            },
                            {
                                "name": "sampling_depth",
                                "type": "Int",
                                "description": "Reads per sample",
                                "signature_type": "parameter",
                                "default": 1000,
                            },
                            {
                                "name": "metadata_file",
                                "type": "Metadata",
                                "description": "Sample metadata",
                                "signature_type": "metadata",
                            },
                        ],
                    },
                },
            }
        }
    )

    data = to_completion_data(catalog)
    action = data.commands[0].actions[0]
    by_name = {parameter.name: parameter.item for parameter in action.parameters}

    assert by_name["visualization"].label == "--o-visualization"
    assert by_name["visualization"].kind == CompletionKind.PARAMETER
    assert by_name["visualization"].detail == (
        "(required) [Visualization] Output visualization"
    )
    assert by_name["sampling_depth"].label == "--p-sampling-depth"
    assert by_name["sampling_depth"].detail == "[Int] Reads per sample"
    assert by_name["metadata_file"].label == "--m-metadata-file"
    assert by_name["metadata_file"].detail == "(required) [Metadata] Sample metadata"


def test_can_import_lsp_package_and_adapter() -> None:
    importlib.import_module("q2lsp.lsp")
    importlib.import_module("q2lsp.adapters.completion_adapter")
