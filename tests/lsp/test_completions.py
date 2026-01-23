"""Tests for completion logic."""

from __future__ import annotations

import pytest

from q2lsp.lsp.completions import (
    CompletionItem,
    get_completions,
    _complete_root,
    _complete_plugin,
    _complete_parameters,
    _get_used_parameters,
)
from q2lsp.lsp.types import CompletionContext, ParsedCommand, TokenSpan


@pytest.fixture
def mock_hierarchy() -> dict:
    """Create a mock QIIME2 command hierarchy for testing."""
    return {
        "qiime": {
            "name": "qiime",
            "help": "QIIME 2 command-line interface",
            "short_help": "QIIME 2 CLI",
            "builtins": ["info", "tools", "dev", "metadata", "types"],
            "info": {
                "name": "info",
                "short_help": "Display information about current deployment",
                "type": "builtin",
            },
            "tools": {
                "name": "tools",
                "short_help": "Tools for working with QIIME 2 files",
                "type": "builtin",
                "import": {
                    "id": "import",
                    "name": "import",
                    "description": "Import data into a new QIIME 2 Artifact",
                    "signature": [],
                },
                "export": {
                    "id": "export",
                    "name": "export",
                    "description": "Export data from a QIIME 2 Artifact or Visualization",
                    "signature": [],
                },
                "peek": {
                    "id": "peek",
                    "name": "peek",
                    "description": "Take a peek at a QIIME 2 Artifact or Visualization",
                    "signature": [],
                },
                "citations": {
                    "id": "citations",
                    "name": "citations",
                    "description": "Print citations for a QIIME 2 result",
                    "signature": [],
                },
                "validate": {
                    "id": "validate",
                    "name": "validate",
                    "description": "Validate data in a QIIME 2 Artifact",
                    "signature": [],
                },
            },
            "metadata": {
                "name": "metadata",
                "short_help": "Plugin for working with Metadata",
                "type": "builtin",
                "distance-matrix": {
                    "id": "distance-matrix",
                    "name": "distance-matrix",
                    "description": "Create a distance matrix from a numeric Metadata column",
                    "signature": [],
                },
                "merge": {
                    "id": "merge",
                    "name": "merge",
                    "description": "Merge metadata",
                    "signature": [],
                },
                "shuffle-groups": {
                    "id": "shuffle-groups",
                    "name": "shuffle-groups",
                    "description": "Shuffle values in a categorical sample metadata column",
                    "signature": [],
                },
                "tabulate": {
                    "id": "tabulate",
                    "name": "tabulate",
                    "description": "Interactively explore Metadata in an HTML table",
                    "signature": [],
                },
            },
            "dev": {
                "name": "dev",
                "short_help": "Utilities for developers and advanced users",
                "type": "builtin",
                "refresh-cache": {
                    "id": "refresh-cache",
                    "name": "refresh-cache",
                    "description": "Refresh CLI cache",
                    "signature": [],
                },
                "reset-theme": {
                    "id": "reset-theme",
                    "name": "reset-theme",
                    "description": "Reset command line theme to default",
                    "signature": [],
                },
            },
            "types": {
                "name": "types",
                "short_help": "Plugin defining types for microbiome analysis",
                "type": "builtin",
                "collate-contigs": {
                    "id": "collate-contigs",
                    "name": "collate-contigs",
                    "description": "Collate contigs",
                    "signature": [],
                },
                "partition-samples-single": {
                    "id": "partition-samples-single",
                    "name": "partition-samples-single",
                    "description": "Split demultiplexed sequence data into partitions",
                    "signature": [],
                },
            },
            "feature-table": {
                "id": "feature-table",
                "name": "feature-table",
                "short_description": "Plugin for working with feature tables",
                "description": "Full description of feature-table plugin",
                "summarize": {
                    "id": "summarize",
                    "name": "summarize",
                    "description": "Summarize a feature table",
                    "signature": [
                        {
                            "name": "table",
                            "type": "FeatureTable",
                            "description": "The feature table to summarize",
                        },
                        {
                            "name": "output_dir",
                            "type": "Path",
                            "description": "Output directory",
                            "default": None,
                        },
                        {
                            "name": "sample_metadata",
                            "type": "Metadata",
                            "description": "Sample metadata",
                            "default": None,
                        },
                    ],
                },
                "filter-samples": {
                    "id": "filter-samples",
                    "name": "filter-samples",
                    "description": "Filter samples from a feature table",
                    "signature": [
                        {
                            "name": "table",
                            "type": "FeatureTable",
                            "description": "Input table",
                        },
                    ],
                },
            },
            "diversity": {
                "id": "diversity",
                "name": "diversity",
                "short_description": "Diversity analyses",
                "alpha": {
                    "id": "alpha",
                    "name": "alpha",
                    "description": "Compute alpha diversity",
                    "signature": [],
                },
            },
        }
    }


class TestCompleteRoot:
    def test_returns_builtins(self, mock_hierarchy: dict) -> None:
        items = _complete_root(mock_hierarchy["qiime"], "")
        labels = [i.label for i in items]
        assert "info" in labels
        assert "tools" in labels
        assert "dev" in labels
        assert "metadata" in labels
        assert "types" in labels

    def test_returns_plugins(self, mock_hierarchy: dict) -> None:
        items = _complete_root(mock_hierarchy["qiime"], "")
        labels = [i.label for i in items]
        assert "feature-table" in labels
        assert "diversity" in labels

    def test_filters_by_prefix(self, mock_hierarchy: dict) -> None:
        items = _complete_root(mock_hierarchy["qiime"], "f")
        labels = [i.label for i in items]
        assert "feature-table" in labels
        assert "info" not in labels
        assert "diversity" not in labels

    def test_builtin_kind(self, mock_hierarchy: dict) -> None:
        items = _complete_root(mock_hierarchy["qiime"], "info")
        assert len(items) == 1
        assert items[0].kind == "builtin"

    def test_plugin_kind(self, mock_hierarchy: dict) -> None:
        items = _complete_root(mock_hierarchy["qiime"], "feature")
        assert len(items) == 1
        assert items[0].kind == "plugin"

    def test_includes_detail(self, mock_hierarchy: dict) -> None:
        items = _complete_root(mock_hierarchy["qiime"], "info")
        assert items[0].detail != ""


class TestCompletePlugin:
    def test_returns_actions(self, mock_hierarchy: dict) -> None:
        items = _complete_plugin(mock_hierarchy["qiime"], "feature-table", "")
        labels = [i.label for i in items]
        assert "summarize" in labels
        assert "filter-samples" in labels

    def test_filters_by_prefix(self, mock_hierarchy: dict) -> None:
        items = _complete_plugin(mock_hierarchy["qiime"], "feature-table", "s")
        labels = [i.label for i in items]
        assert "summarize" in labels
        assert "filter-samples" not in labels

    def test_action_kind(self, mock_hierarchy: dict) -> None:
        items = _complete_plugin(mock_hierarchy["qiime"], "feature-table", "summarize")
        assert len(items) == 1
        assert items[0].kind == "action"

    def test_unknown_plugin_returns_empty(self, mock_hierarchy: dict) -> None:
        items = _complete_plugin(mock_hierarchy["qiime"], "nonexistent", "")
        assert items == []

    def test_builtin_returns_help_option(self, mock_hierarchy: dict) -> None:
        items = _complete_plugin(mock_hierarchy["qiime"], "info", "")
        labels = [i.label for i in items]
        assert "--help" in labels

    def test_builtin_with_actions_returns_actions(self, mock_hierarchy: dict) -> None:
        """Test that builtins with actions return their subcommands, not just --help."""
        items = _complete_plugin(mock_hierarchy["qiime"], "tools", "")
        labels = [i.label for i in items]
        # Should return the tool subcommands, not just --help
        assert "import" in labels
        assert "export" in labels
        assert "peek" in labels
        assert "citations" in labels
        assert "validate" in labels

    def test_builtin_with_actions_filters_by_prefix(self, mock_hierarchy: dict) -> None:
        """Test that prefix filtering works for builtin actions."""
        items = _complete_plugin(mock_hierarchy["qiime"], "tools", "i")
        labels = [i.label for i in items]
        assert "import" in labels
        assert "export" not in labels
        assert "peek" not in labels

    def test_builtin_types_returns_actions(self, mock_hierarchy: dict) -> None:
        """Test that 'types' builtin returns its subcommands."""
        items = _complete_plugin(mock_hierarchy["qiime"], "types", "")
        labels = [i.label for i in items]
        assert "collate-contigs" in labels
        assert "partition-samples-single" in labels

    def test_builtin_metadata_returns_actions(self, mock_hierarchy: dict) -> None:
        """Test that 'metadata' builtin returns its subcommands."""
        items = _complete_plugin(mock_hierarchy["qiime"], "metadata", "")
        labels = [i.label for i in items]
        assert "distance-matrix" in labels
        assert "merge" in labels
        assert "shuffle-groups" in labels
        assert "tabulate" in labels

    def test_builtin_dev_returns_actions(self, mock_hierarchy: dict) -> None:
        """Test that 'dev' builtin returns its subcommands."""
        items = _complete_plugin(mock_hierarchy["qiime"], "dev", "")
        labels = [i.label for i in items]
        assert "refresh-cache" in labels
        assert "reset-theme" in labels

    def test_builtin_action_kind(self, mock_hierarchy: dict) -> None:
        """Test that builtin actions have the 'action' kind."""
        items = _complete_plugin(mock_hierarchy["qiime"], "tools", "import")
        assert len(items) == 1
        assert items[0].kind == "action"

    def test_builtin_with_actions_no_matching_prefix_returns_empty(
        self, mock_hierarchy: dict
    ) -> None:
        """Test that builtin with actions returns empty list when no actions match prefix."""
        items = _complete_plugin(mock_hierarchy["qiime"], "tools", "xyz")
        # Should return empty list, not --help, because tools has actions
        assert items == []


class TestCompleteParameters:
    def test_returns_parameters(self, mock_hierarchy: dict) -> None:
        items = _complete_parameters(
            mock_hierarchy["qiime"], "feature-table", "summarize", "--", set()
        )
        labels = [i.label for i in items]
        assert "--table" in labels
        assert "--output-dir" in labels
        assert "--sample-metadata" in labels

    def test_filters_by_prefix(self, mock_hierarchy: dict) -> None:
        items = _complete_parameters(
            mock_hierarchy["qiime"], "feature-table", "summarize", "--t", set()
        )
        labels = [i.label for i in items]
        assert "--table" in labels
        assert "--output-dir" not in labels

    def test_excludes_used_parameters(self, mock_hierarchy: dict) -> None:
        items = _complete_parameters(
            mock_hierarchy["qiime"], "feature-table", "summarize", "--", {"table"}
        )
        labels = [i.label for i in items]
        assert "--table" not in labels
        assert "--output-dir" in labels

    def test_includes_help(self, mock_hierarchy: dict) -> None:
        items = _complete_parameters(
            mock_hierarchy["qiime"], "feature-table", "summarize", "--", set()
        )
        labels = [i.label for i in items]
        assert "--help" in labels

    def test_parameter_kind(self, mock_hierarchy: dict) -> None:
        items = _complete_parameters(
            mock_hierarchy["qiime"], "feature-table", "summarize", "--table", set()
        )
        assert len(items) == 1
        assert items[0].kind == "parameter"

    def test_required_indicator(self, mock_hierarchy: dict) -> None:
        items = _complete_parameters(
            mock_hierarchy["qiime"], "feature-table", "summarize", "--table", set()
        )
        # table has no default, so it's required
        assert "(required)" in items[0].detail


class TestGetUsedParameters:
    def test_extracts_used_params(self) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--table", 30, 37),
            TokenSpan("table.qza", 38, 47),
            TokenSpan("--output-dir", 48, 60),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=60)
        ctx = CompletionContext(
            mode="parameter", command=cmd, current_token=None, token_index=6, prefix=""
        )
        used = _get_used_parameters(ctx)
        assert "table" in used
        assert "output_dir" in used  # normalized to underscore

    def test_handles_equals_syntax(self) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--table=table.qza", 30, 47),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=47)
        ctx = CompletionContext(
            mode="parameter", command=cmd, current_token=None, token_index=4, prefix=""
        )
        used = _get_used_parameters(ctx)
        assert "table" in used


class TestGetCompletions:
    def test_mode_none_returns_empty(self, mock_hierarchy: dict) -> None:
        ctx = CompletionContext(
            mode="none", command=None, current_token=None, token_index=-1, prefix=""
        )
        items = get_completions(ctx, mock_hierarchy)
        assert items == []

    def test_mode_root(self, mock_hierarchy: dict) -> None:
        tokens = [TokenSpan("qiime", 0, 5)]
        cmd = ParsedCommand(tokens=tokens, start=0, end=6)
        ctx = CompletionContext(
            mode="root", command=cmd, current_token=None, token_index=1, prefix=""
        )
        items = get_completions(ctx, mock_hierarchy)
        labels = [i.label for i in items]
        assert "info" in labels
        assert "feature-table" in labels

    def test_mode_plugin(self, mock_hierarchy: dict) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=20)
        ctx = CompletionContext(
            mode="plugin", command=cmd, current_token=None, token_index=2, prefix=""
        )
        items = get_completions(ctx, mock_hierarchy)
        labels = [i.label for i in items]
        assert "summarize" in labels

    def test_mode_parameter(self, mock_hierarchy: dict) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=30)
        ctx = CompletionContext(
            mode="parameter",
            command=cmd,
            current_token=None,
            token_index=3,
            prefix="--",
        )
        items = get_completions(ctx, mock_hierarchy)
        labels = [i.label for i in items]
        assert "--table" in labels
