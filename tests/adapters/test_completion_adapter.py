"""Tests for completion adapter."""

from __future__ import annotations

import importlib

from q2lsp.adapters.completion_adapter import (
    get_used_parameters,
    to_completion_data,
    to_completion_query,
)
from q2lsp.core.types import COMPLETION_MODE_NONE, COMPLETION_MODE_PARAMETER


def test_maps_boundary_values_to_core_query() -> None:
    query = to_completion_query(
        mode="parameter",
        prefix="--",
        command_tokens=("qiime", "feature-table", "summarize", "--"),
    )

    assert query.mode == COMPLETION_MODE_PARAMETER
    assert query.prefix == "--"
    assert query.normalized_prefix == ""
    assert query.plugin_name == "feature-table"
    assert query.action_name == "summarize"
    assert query.used_parameters == frozenset()


def test_unknown_mode_maps_to_none() -> None:
    query = to_completion_query(mode="unknown", prefix="", command_tokens=())

    assert query.mode == COMPLETION_MODE_NONE
    assert query.plugin_name == ""
    assert query.action_name == ""


def test_empty_tokens_maps_to_none_mode() -> None:
    query = to_completion_query(mode="root", prefix="", command_tokens=())

    assert query.mode == COMPLETION_MODE_NONE


def test_get_used_parameters_ignores_empty_option_stub() -> None:
    used = get_used_parameters(
        ("qiime", "feature-table", "summarize", "--", "--i-table", "x")
    )

    assert used == {"table"}


def test_normalizes_hierarchy_to_core_data() -> None:
    hierarchy = {
        "qiime": {
            "builtins": ["info"],
            "info": {
                "short_help": "Display information",
            },
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

    data = to_completion_data(hierarchy)

    assert {item.label for item in data.root_items} == {"info", "feature-table"}
    command_names = {command.name for command in data.commands}
    assert command_names == {"info", "feature-table"}


def test_can_import_lsp_completions_and_adapter() -> None:
    importlib.import_module("q2lsp.lsp.completions")
    importlib.import_module("q2lsp.adapters.completion_adapter")
