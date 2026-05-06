"""Cross-feature consistency tests for completions and diagnostics."""

from __future__ import annotations

import pytest

from tests.helpers.completions import (
    complete_parameters,
    complete_plugin,
    complete_root,
)

from q2lsp.core.types import CompletionItem
from q2lsp.lsp.diagnostics.codes import (
    MISSING_REQUIRED_OPTION,
    UNKNOWN_ACTION,
    UNKNOWN_OPTION,
    UNKNOWN_SUBCOMMAND,
)
from q2lsp.lsp.diagnostics.validator import validate_command_with_catalog
from q2lsp.lsp.types import ParsedCommand, TokenSpan
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.signature_params import (
    get_all_option_labels,
    get_required_option_labels,
)
from q2lsp.qiime.types import CommandHierarchy


def _labels(items: list[CompletionItem]) -> set[str]:
    return {item.label for item in items}


def _build_parsed_command(token_texts: list[str]) -> ParsedCommand:
    """Build a ParsedCommand with space-delimited token spans."""
    tokens: list[TokenSpan] = []
    offset = 0

    for token_text in token_texts:
        start = offset
        end = start + len(token_text)
        tokens.append(TokenSpan(token_text, start, end))
        offset = end + 1

    end_offset = tokens[-1].end if tokens else 0
    return ParsedCommand(tokens=tokens, start=0, end=end_offset)


def _issue_codes(token_texts: list[str], catalog: QiimeCatalog) -> list[str]:
    command = _build_parsed_command(token_texts)
    return [issue.code for issue in validate_command_with_catalog(command, catalog)]


@pytest.fixture
def shared_hierarchy() -> CommandHierarchy:
    """Hierarchy shared between completions and diagnostics tests."""
    return {
        "qiime": {
            "name": "qiime",
            "help": "QIIME 2 CLI",
            "short_help": "CLI",
            "builtins": ["info", "tools"],
            "info": {
                "name": "info",
                "short_help": "Display info",
                "type": "builtin",
            },
            "tools": {
                "name": "tools",
                "short_help": "Tools",
                "type": "builtin",
                "import": {
                    "id": "import",
                    "name": "import",
                    "description": "Import data",
                    "signature": [
                        {
                            "name": "input_path",
                            "signature_type": "parameter",
                            "description": "Path to import",
                        },
                        {
                            "name": "output_path",
                            "signature_type": "parameter",
                            "description": "Output path",
                            "default": None,
                        },
                    ],
                },
            },
            "diversity": {
                "id": "diversity",
                "name": "diversity",
                "short_description": "Diversity analysis",
                "core-metrics": {
                    "id": "core-metrics",
                    "name": "core-metrics",
                    "description": "Core diversity metrics",
                    "signature": [
                        {
                            "name": "table",
                            "signature_type": "input",
                            "description": "Feature table",
                        },
                        {
                            "name": "phylogeny",
                            "signature_type": "input",
                            "description": "Phylogenetic tree",
                        },
                        {
                            "name": "sampling_depth",
                            "signature_type": "parameter",
                            "description": "Sampling depth",
                        },
                        {
                            "name": "metadata",
                            "signature_type": "metadata",
                            "description": "Sample metadata",
                        },
                        {
                            "name": "n_jobs",
                            "signature_type": "parameter",
                            "description": "Number of jobs",
                            "default": 1,
                        },
                    ],
                },
            },
        },
    }


class TestCompletionsDiagnosticsConsistency:
    """Cross-feature tests ensuring completions and diagnostics agree."""

    def test_option_labels_match_between_features(
        self, shared_hierarchy: CommandHierarchy
    ) -> None:
        """Completion option labels == diagnostic valid options for same action."""
        root_node = shared_hierarchy["qiime"]
        action_node = root_node["diversity"]["core-metrics"]

        completion_items = complete_parameters(
            root_node,
            "diversity",
            "core-metrics",
            "",
            set(),
        )
        completion_labels = {
            item.label for item in completion_items if item.label != "--help"
        }

        diagnostic_labels = set(get_all_option_labels(action_node))

        assert completion_labels == diagnostic_labels

        catalog = QiimeCatalog.from_hierarchy(shared_hierarchy)
        for option_label in completion_labels:
            issue_codes = _issue_codes(
                ["qiime", "diversity", "core-metrics", option_label, "value"],
                catalog,
            )
            assert UNKNOWN_OPTION not in issue_codes

    def test_required_options_match_between_features(
        self, shared_hierarchy: CommandHierarchy
    ) -> None:
        """Required options identified by completions match diagnostics required set."""
        root_node = shared_hierarchy["qiime"]
        action_node = root_node["diversity"]["core-metrics"]

        completion_items = complete_parameters(
            root_node,
            "diversity",
            "core-metrics",
            "",
            set(),
        )
        required_from_completions = {
            item.label for item in completion_items if "(required)" in item.detail
        }

        required_from_diagnostics = set(get_required_option_labels(action_node))

        assert required_from_completions == required_from_diagnostics

        catalog = QiimeCatalog.from_hierarchy(shared_hierarchy)
        missing_metadata_codes = _issue_codes(
            [
                "qiime",
                "diversity",
                "core-metrics",
                "--i-table",
                "x",
                "--i-phylogeny",
                "y",
                "--p-sampling-depth",
                "100",
            ],
            catalog,
        )
        complete_codes = _issue_codes(
            [
                "qiime",
                "diversity",
                "core-metrics",
                "--i-table",
                "x",
                "--i-phylogeny",
                "y",
                "--p-sampling-depth",
                "100",
                "--m-metadata",
                "m",
            ],
            catalog,
        )

        assert MISSING_REQUIRED_OPTION in missing_metadata_codes
        assert MISSING_REQUIRED_OPTION not in complete_codes

    def test_plugin_names_match_between_features(
        self, shared_hierarchy: CommandHierarchy
    ) -> None:
        """Plugin/builtin names from completions match diagnostics valid names."""
        root_node = shared_hierarchy["qiime"]
        catalog = QiimeCatalog.from_hierarchy(shared_hierarchy)

        completion_names = _labels(complete_root(root_node, ""))
        valid_plugins, valid_builtins = catalog.valid_plugins_and_builtins()

        assert completion_names == (valid_plugins | valid_builtins)

    def test_action_names_match_between_features(
        self, shared_hierarchy: CommandHierarchy
    ) -> None:
        """Action names from completions match diagnostics valid actions."""
        root_node = shared_hierarchy["qiime"]
        catalog = QiimeCatalog.from_hierarchy(shared_hierarchy)

        completion_action_names = _labels(complete_plugin(root_node, "diversity", ""))
        valid_actions = set(catalog.valid_actions("diversity"))

        assert completion_action_names == valid_actions

        for action_name in completion_action_names:
            command = _build_parsed_command(["qiime", "diversity", action_name])
            issues = validate_command_with_catalog(command, catalog)
            unknown_action_issues = [
                issue for issue in issues if issue.code == UNKNOWN_ACTION
            ]
            assert unknown_action_issues == []

        unknown_action_name = "not-a-real-action"
        command = _build_parsed_command(["qiime", "diversity", unknown_action_name])
        issues = validate_command_with_catalog(command, catalog)
        unknown_action_issues = [
            issue for issue in issues if issue.code == UNKNOWN_ACTION
        ]

        assert unknown_action_name not in completion_action_names
        assert len(unknown_action_issues) == 1

    def test_builtin_subcommand_names_match_between_features(
        self, shared_hierarchy: CommandHierarchy
    ) -> None:
        """Builtin subcommands from completions are accepted by diagnostics."""
        root_node = shared_hierarchy["qiime"]
        catalog = QiimeCatalog.from_hierarchy(shared_hierarchy)

        completion_subcommands = _labels(complete_plugin(root_node, "tools", ""))
        valid_codes = _issue_codes(["qiime", "tools", "import"], catalog)
        unknown_codes = _issue_codes(["qiime", "tools", "not-a-real-tool"], catalog)

        assert "import" in completion_subcommands
        assert UNKNOWN_SUBCOMMAND not in valid_codes
        assert UNKNOWN_SUBCOMMAND in unknown_codes

    def test_valid_command_has_no_diagnostics_and_has_completions(
        self, shared_hierarchy: CommandHierarchy
    ) -> None:
        """A valid command with all required options has no diagnostics, but completions available."""
        root_node = shared_hierarchy["qiime"]
        catalog = QiimeCatalog.from_hierarchy(shared_hierarchy)
        command = _build_parsed_command(
            [
                "qiime",
                "diversity",
                "core-metrics",
                "--i-table",
                "x",
                "--i-phylogeny",
                "y",
                "--p-sampling-depth",
                "100",
                "--m-metadata",
                "m",
            ]
        )

        issues = validate_command_with_catalog(command, catalog)
        assert issues == []

        completion_items = complete_parameters(
            root_node,
            "diversity",
            "core-metrics",
            "--",
            {"table", "phylogeny", "sampling_depth", "metadata"},
        )
        remaining_labels = _labels(completion_items)

        assert "--p-n-jobs" in remaining_labels
        assert "--help" in remaining_labels
