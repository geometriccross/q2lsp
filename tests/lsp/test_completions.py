"""Tests for completion logic."""

from __future__ import annotations

import pytest

from tests.helpers.cursor import extract_cursor_offset

from q2lsp.lsp.completions import (
    CompletionItem,
    get_completions,
    _complete_root,
    _complete_plugin,
    _complete_parameters,
    _get_used_parameters,
)
from q2lsp.lsp.types import (
    CompletionContext,
    CompletionMode,
    ParsedCommand,
    TokenSpan,
)


def labels(items: list[CompletionItem]) -> list[str]:
    """Extract labels from completion items."""
    return [item.label for item in items]


def assert_labels(
    items: list[CompletionItem],
    expected_labels: set[str] | list[str],
) -> None:
    """Assert that items contain all expected labels (unordered)."""
    expected = set(expected_labels)
    actual = set(labels(items))
    assert actual == expected, f"Expected {expected}, got {actual}"


@pytest.fixture
def hierarchy_root_builtins() -> dict:
    """Minimal hierarchy with root builtins for testing."""
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
        }
    }


@pytest.fixture
def hierarchy_with_plugins() -> dict:
    """Hierarchy with plugins for testing plugin completion."""
    return {
        "qiime": {
            "name": "qiime",
            "help": "QIIME 2 command-line interface",
            "short_help": "QIIME 2 CLI",
            "builtins": ["info"],
            "info": {
                "name": "info",
                "short_help": "Display information about current deployment",
                "type": "builtin",
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
                            "signature_type": "input",
                        },
                        {
                            "name": "output_dir",
                            "type": "Path",
                            "description": "Output directory",
                            "default": None,
                            "signature_type": "output",
                        },
                        {
                            "name": "sample_metadata",
                            "type": "Metadata",
                            "description": "Sample metadata",
                            "default": None,
                            "signature_type": "parameter",
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
                            "signature_type": "input",
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


@pytest.fixture
def hierarchy_with_parameters() -> dict:
    """Hierarchy with action parameters for testing parameter completion."""
    return {
        "qiime": {
            "name": "qiime",
            "help": "QIIME 2 command-line interface",
            "short_help": "QIIME 2 CLI",
            "builtins": ["info"],
            "info": {
                "name": "info",
                "short_help": "Display information about current deployment",
                "type": "builtin",
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
                            "signature_type": "input",
                        },
                        {
                            "name": "output_dir",
                            "type": "Path",
                            "description": "Output directory",
                            "default": None,
                            "signature_type": "output",
                        },
                        {
                            "name": "sample_metadata",
                            "type": "Metadata",
                            "description": "Sample metadata",
                            "default": None,
                            "signature_type": "parameter",
                        },
                    ],
                },
            },
        }
    }


@pytest.fixture
def full_mock_hierarchy() -> dict:
    """Complete mock hierarchy for comprehensive tests."""
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
            },
            "metadata": {
                "name": "metadata",
                "short_help": "Plugin for working with Metadata",
                "type": "builtin",
                "tabulate": {
                    "id": "tabulate",
                    "name": "tabulate",
                    "description": "Interactively explore Metadata in an HTML table",
                    "signature": [],
                },
            },
            "feature-table": {
                "id": "feature-table",
                "name": "feature-table",
                "short_description": "Plugin for working with feature tables",
                "summarize": {
                    "id": "summarize",
                    "name": "summarize",
                    "description": "Summarize a feature table",
                    "signature": [
                        {
                            "name": "table",
                            "type": "FeatureTable",
                            "description": "The feature table to summarize",
                            "signature_type": "input",
                        },
                        {
                            "name": "output_dir",
                            "type": "Path",
                            "description": "Output directory",
                            "default": None,
                            "signature_type": "output",
                        },
                        {
                            "name": "sample_metadata",
                            "type": "Metadata",
                            "description": "Sample metadata",
                            "default": None,
                            "signature_type": "parameter",
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
    def test_returns_builtins(self, hierarchy_root_builtins: dict) -> None:
        items = _complete_root(hierarchy_root_builtins["qiime"], "")
        assert_labels(items, {"info", "tools", "dev", "metadata", "types"})

    def test_returns_plugins(self, hierarchy_with_plugins: dict) -> None:
        items = _complete_root(hierarchy_with_plugins["qiime"], "")
        assert_labels(items, {"info", "feature-table", "diversity"})

    def test_filters_by_prefix(self, hierarchy_with_plugins: dict) -> None:
        items = _complete_root(hierarchy_with_plugins["qiime"], "f")
        assert_labels(items, {"feature-table"})

    def test_builtin_kind(self, hierarchy_root_builtins: dict) -> None:
        items = _complete_root(hierarchy_root_builtins["qiime"], "info")
        assert len(items) == 1
        assert items[0].kind == "builtin"

    def test_plugin_kind(self, hierarchy_with_plugins: dict) -> None:
        items = _complete_root(hierarchy_with_plugins["qiime"], "feature")
        assert len(items) == 1
        assert items[0].kind == "plugin"

    def test_includes_detail(self, hierarchy_root_builtins: dict) -> None:
        items = _complete_root(hierarchy_root_builtins["qiime"], "info")
        assert items[0].detail != ""


class TestCompletePlugin:
    def test_returns_actions(self, hierarchy_with_plugins: dict) -> None:
        items = _complete_plugin(hierarchy_with_plugins["qiime"], "feature-table", "")
        assert_labels(items, {"summarize", "filter-samples"})

    def test_filters_by_prefix(self, hierarchy_with_plugins: dict) -> None:
        items = _complete_plugin(hierarchy_with_plugins["qiime"], "feature-table", "s")
        assert_labels(items, {"summarize"})

    def test_action_kind(self, hierarchy_with_plugins: dict) -> None:
        items = _complete_plugin(
            hierarchy_with_plugins["qiime"], "feature-table", "summarize"
        )
        assert len(items) == 1
        assert items[0].kind == "action"

    def test_unknown_plugin_returns_empty(self, hierarchy_with_plugins: dict) -> None:
        items = _complete_plugin(hierarchy_with_plugins["qiime"], "nonexistent", "")
        assert items == []

    def test_builtin_returns_help_option(self, hierarchy_with_plugins: dict) -> None:
        items = _complete_plugin(hierarchy_with_plugins["qiime"], "info", "")
        assert_labels(items, {"--help"})

    def test_builtin_with_actions_returns_actions(
        self, hierarchy_root_builtins: dict
    ) -> None:
        """Test that builtins with actions return their subcommands, not just --help."""
        items = _complete_plugin(hierarchy_root_builtins["qiime"], "tools", "")
        assert_labels(items, {"import", "export", "peek", "citations", "validate"})

    def test_builtin_with_actions_filters_by_prefix(
        self, hierarchy_root_builtins: dict
    ) -> None:
        """Test that prefix filtering works for builtin actions."""
        items = _complete_plugin(hierarchy_root_builtins["qiime"], "tools", "i")
        assert_labels(items, {"import"})

    def test_builtin_types_returns_actions(self, hierarchy_root_builtins: dict) -> None:
        """Test that 'types' builtin returns its subcommands."""
        items = _complete_plugin(hierarchy_root_builtins["qiime"], "types", "")
        assert_labels(items, {"collate-contigs", "partition-samples-single"})

    def test_builtin_metadata_returns_actions(
        self, hierarchy_root_builtins: dict
    ) -> None:
        """Test that 'metadata' builtin returns its subcommands."""
        items = _complete_plugin(hierarchy_root_builtins["qiime"], "metadata", "")
        assert_labels(items, {"distance-matrix", "merge", "shuffle-groups", "tabulate"})

    def test_builtin_dev_returns_actions(self, hierarchy_root_builtins: dict) -> None:
        """Test that 'dev' builtin returns its subcommands."""
        items = _complete_plugin(hierarchy_root_builtins["qiime"], "dev", "")
        assert_labels(items, {"refresh-cache", "reset-theme"})

    def test_builtin_action_kind(self, hierarchy_root_builtins: dict) -> None:
        """Test that builtin actions have the 'action' kind."""
        items = _complete_plugin(hierarchy_root_builtins["qiime"], "tools", "import")
        assert len(items) == 1
        assert items[0].kind == "action"

    def test_builtin_with_actions_no_matching_prefix_returns_empty(
        self, hierarchy_root_builtins: dict
    ) -> None:
        """Test that builtin with actions returns empty list when no actions match prefix."""
        items = _complete_plugin(hierarchy_root_builtins["qiime"], "tools", "xyz")
        # Should return empty list, not --help, because tools has actions
        assert items == []


class TestCompleteParameters:
    def test_returns_parameters(self, hierarchy_with_parameters: dict) -> None:
        items = _complete_parameters(
            hierarchy_with_parameters["qiime"],
            "feature-table",
            "summarize",
            "--",
            set(),
        )
        assert_labels(
            items, {"--i-table", "--o-output-dir", "--p-sample-metadata", "--help"}
        )

    def test_filters_by_prefix(self, hierarchy_with_parameters: dict) -> None:
        items = _complete_parameters(
            hierarchy_with_parameters["qiime"],
            "feature-table",
            "summarize",
            "--t",
            set(),
        )
        assert_labels(items, {"--i-table"})

    def test_excludes_used_parameters(self, hierarchy_with_parameters: dict) -> None:
        items = _complete_parameters(
            hierarchy_with_parameters["qiime"],
            "feature-table",
            "summarize",
            "--",
            {"table"},
        )
        assert "--i-table" not in labels(items)
        assert "--o-output-dir" in labels(items)

    def test_includes_help(self, hierarchy_with_parameters: dict) -> None:
        items = _complete_parameters(
            hierarchy_with_parameters["qiime"],
            "feature-table",
            "summarize",
            "--",
            set(),
        )
        assert "--help" in labels(items)

    def test_parameter_kind(self, hierarchy_with_parameters: dict) -> None:
        items = _complete_parameters(
            hierarchy_with_parameters["qiime"],
            "feature-table",
            "summarize",
            "--i-table",
            set(),
        )
        assert len(items) == 1
        assert items[0].kind == "parameter"

    def test_required_indicator(self, hierarchy_with_parameters: dict) -> None:
        items = _complete_parameters(
            hierarchy_with_parameters["qiime"],
            "feature-table",
            "summarize",
            "--i-table",
            set(),
        )
        # table has no default, so it's required
        assert "(required)" in items[0].detail


class TestGetUsedParameters:
    def test_extracts_used_params(self) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--i-table", 30, 39),
            TokenSpan("table.qza", 40, 49),
            TokenSpan("--o-output-dir", 50, 64),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=64)
        ctx = CompletionContext(
            mode=CompletionMode.PARAMETER,
            command=cmd,
            current_token=None,
            token_index=6,
            prefix="",
        )
        used = _get_used_parameters(ctx)
        assert "table" in used
        assert "output_dir" in used  # normalized to underscore

    def test_handles_equals_syntax(self) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--i-table=table.qza", 30, 49),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=49)
        ctx = CompletionContext(
            mode=CompletionMode.PARAMETER,
            command=cmd,
            current_token=None,
            token_index=4,
            prefix="",
        )
        used = _get_used_parameters(ctx)
        assert "table" in used


class TestCompletionPipeline:
    """Integration-style tests for the full completion pipeline."""

    def test_root_mode_pipeline(self, hierarchy_with_plugins: dict) -> None:
        """Text with cursor -> context -> completions at root mode."""
        from q2lsp.lsp.completion_context import get_completion_context

        text, offset = extract_cursor_offset(text_with_cursor="qiime feat<CURSOR>")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.ROOT
        assert ctx.prefix == "feat"

        items = get_completions(ctx, hierarchy_with_plugins)
        assert_labels(items, {"feature-table"})

    def test_plugin_mode_pipeline(self, hierarchy_with_plugins: dict) -> None:
        """Text with cursor -> context -> completions at plugin mode."""
        from q2lsp.lsp.completion_context import get_completion_context

        text, offset = extract_cursor_offset(
            text_with_cursor="qiime feature-table <CURSOR>"
        )
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.PLUGIN
        assert ctx.prefix == ""

        items = get_completions(ctx, hierarchy_with_plugins)
        assert_labels(items, {"summarize", "filter-samples"})

    def test_parameter_mode_pipeline(self, hierarchy_with_parameters: dict) -> None:
        """Text with cursor -> context -> completions at parameter mode."""
        from q2lsp.lsp.completion_context import get_completion_context

        text, offset = extract_cursor_offset(
            text_with_cursor="qiime feature-table summarize --<CURSOR>"
        )
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.PARAMETER
        assert ctx.prefix == "--"

        items = get_completions(ctx, hierarchy_with_parameters)
        item_labels = labels(items)
        assert "--i-table" in item_labels
        assert "--help" in item_labels

    def test_none_mode_pipeline(self, hierarchy_with_plugins: dict) -> None:
        """Text with cursor -> context -> completions at none mode (outside qiime)."""
        from q2lsp.lsp.completion_context import get_completion_context

        text, offset = extract_cursor_offset(text_with_cursor="echo hel<CURSOR>lo")
        ctx = get_completion_context(text, offset)
        assert ctx.mode == CompletionMode.NONE

        items = get_completions(ctx, hierarchy_with_plugins)
        assert items == []


class TestGetCompletions:
    def test_mode_none_returns_empty(self, full_mock_hierarchy: dict) -> None:
        ctx = CompletionContext(
            mode=CompletionMode.NONE,
            command=None,
            current_token=None,
            token_index=-1,
            prefix="",
        )
        items = get_completions(ctx, full_mock_hierarchy)
        assert items == []

    def test_mode_root(self, full_mock_hierarchy: dict) -> None:
        tokens = [TokenSpan("qiime", 0, 5)]
        cmd = ParsedCommand(tokens=tokens, start=0, end=6)
        ctx = CompletionContext(
            mode=CompletionMode.ROOT,
            command=cmd,
            current_token=None,
            token_index=1,
            prefix="",
        )
        items = get_completions(ctx, full_mock_hierarchy)
        assert "info" in labels(items)
        assert "feature-table" in labels(items)

    def test_mode_plugin(self, full_mock_hierarchy: dict) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=20)
        ctx = CompletionContext(
            mode=CompletionMode.PLUGIN,
            command=cmd,
            current_token=None,
            token_index=2,
            prefix="",
        )
        items = get_completions(ctx, full_mock_hierarchy)
        assert "summarize" in labels(items)

    def test_mode_parameter(self, full_mock_hierarchy: dict) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=30)
        ctx = CompletionContext(
            mode=CompletionMode.PARAMETER,
            command=cmd,
            current_token=None,
            token_index=3,
            prefix="--",
        )
        items = get_completions(ctx, full_mock_hierarchy)
        assert "--i-table" in labels(items)
