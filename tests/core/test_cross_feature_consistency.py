"""Cross-feature consistency tests for completions and diagnostics."""

from __future__ import annotations

import pytest

from tests.helpers.completions import complete

from q2lsp.core.types import CompletionItem
from q2lsp.core.diagnostics.codes import (
    MISSING_REQUIRED_OPTION,
    UNKNOWN_ACTION,
    UNKNOWN_OPTION,
    UNKNOWN_SUBCOMMAND,
)
from q2lsp.core.diagnostics import collect_diagnostics
from q2lsp.core.document import analyze_document
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.types import CommandHierarchy


def _labels(items: list[CompletionItem]) -> set[str]:
    return {item.label for item in items}


def _issue_codes(token_texts: list[str], catalog: QiimeCatalog) -> list[str]:
    document = analyze_document(" ".join(token_texts))
    return [issue.code for issue in collect_diagnostics(document, catalog)]


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
                            "type": "parameter",
                            "metadata": "file",
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
        catalog = QiimeCatalog.from_hierarchy(shared_hierarchy)

        completion_items = complete("qiime diversity core-metrics ", catalog)
        completion_labels = {
            item.label for item in completion_items if item.label != "--help"
        }

        assert completion_labels == {
            "--i-table",
            "--i-phylogeny",
            "--p-sampling-depth",
            "--m-metadata-file",
            "--p-n-jobs",
        }

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
        catalog = QiimeCatalog.from_hierarchy(shared_hierarchy)

        completion_items = complete("qiime diversity core-metrics ", catalog)
        required_from_completions = {
            item.label for item in completion_items if "(required)" in item.detail
        }

        assert required_from_completions == {
            "--i-table",
            "--i-phylogeny",
            "--p-sampling-depth",
            "--m-metadata-file",
        }

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
                "--m-metadata-file",
                "m",
            ],
            catalog,
        )

        assert MISSING_REQUIRED_OPTION in missing_metadata_codes
        assert MISSING_REQUIRED_OPTION not in complete_codes

    def test_action_names_match_between_features(
        self, shared_hierarchy: CommandHierarchy
    ) -> None:
        """Action names from completions match diagnostics valid actions."""
        catalog = QiimeCatalog.from_hierarchy(shared_hierarchy)

        completion_action_names = _labels(complete("qiime diversity ", catalog))
        assert completion_action_names == {"core-metrics"}

        for action_name in completion_action_names:
            assert UNKNOWN_ACTION not in _issue_codes(
                ["qiime", "diversity", action_name], catalog
            )

        unknown_action_name = "not-a-real-action"
        assert unknown_action_name not in completion_action_names
        assert UNKNOWN_ACTION in _issue_codes(
            ["qiime", "diversity", unknown_action_name], catalog
        )

    def test_builtin_subcommand_names_match_between_features(
        self, shared_hierarchy: CommandHierarchy
    ) -> None:
        """Builtin subcommands from completions are accepted by diagnostics."""
        catalog = QiimeCatalog.from_hierarchy(shared_hierarchy)

        completion_subcommands = _labels(complete("qiime tools ", catalog))
        valid_codes = _issue_codes(["qiime", "tools", "import"], catalog)
        unknown_codes = _issue_codes(["qiime", "tools", "not-a-real-tool"], catalog)

        assert "import" in completion_subcommands
        assert UNKNOWN_SUBCOMMAND not in valid_codes
        assert UNKNOWN_SUBCOMMAND in unknown_codes

    def test_valid_command_has_no_diagnostics_and_has_completions(
        self, shared_hierarchy: CommandHierarchy
    ) -> None:
        """A valid command with all required options has no diagnostics, but completions available."""
        catalog = QiimeCatalog.from_hierarchy(shared_hierarchy)
        source = " ".join(
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
                "--m-metadata-file",
                "m",
            ]
        )

        assert collect_diagnostics(analyze_document(source), catalog) == []

        completion_items = complete(source + " --", catalog)
        remaining_labels = _labels(completion_items)

        assert "--p-n-jobs" in remaining_labels
        assert "--help" in remaining_labels
