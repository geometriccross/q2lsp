"""Tests for diagnostics validator module."""

from __future__ import annotations

import pytest

from q2lsp.lsp.diagnostics.matching import (
    _get_close_matches,
    _get_suggestions,
    _is_exact_match,
)
from q2lsp.lsp.diagnostics.validator import validate_command
from q2lsp.lsp.types import ParsedCommand, TokenSpan


@pytest.fixture
def hierarchy_with_plugins_and_builtins() -> dict:
    """Hierarchy with plugins and builtins for testing."""
    return {
        "qiime": {
            "name": "qiime",
            "help": "QIIME 2 command-line interface",
            "short_help": "QIIME 2 CLI",
            "builtins": ["info", "tools", "dev"],
            "info": {
                "name": "info",
                "short_help": "Display information",
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
                },
                "export": {
                    "id": "export",
                    "name": "export",
                    "description": "Export data",
                },
            },
            "dev": {
                "name": "dev",
                "short_help": "Dev tools",
                "type": "builtin",
                "refresh-cache": {
                    "id": "refresh-cache",
                    "name": "refresh-cache",
                    "description": "Refresh cache",
                },
            },
            "metadata": {
                "name": "metadata",
                "short_help": "Metadata operations",
                "tabulate": {
                    "id": "tabulate",
                    "name": "tabulate",
                    "description": "Tabulate metadata",
                    "signature": [
                        {
                            "name": "metadata",
                            "type": "input",
                        },
                        {
                            "name": "output_path",
                            "type": "parameter",
                        },
                    ],
                },
            },
            "feature-table": {
                "id": "feature-table",
                "name": "feature-table",
                "short_description": "Plugin for feature tables",
                "summarize": {
                    "id": "summarize",
                    "name": "summarize",
                    "description": "Summarize table",
                    "signature": [
                        {
                            "name": "table",
                            "type": "input",
                        },
                        {
                            "name": "obs_metadata",
                            "type": "parameter",
                            "default": None,
                        },
                    ],
                },
                "filter-samples": {
                    "id": "filter-samples",
                    "name": "filter-samples",
                    "description": "Filter samples",
                    "signature": [
                        {
                            "name": "table",
                            "type": "input",
                        },
                        {
                            "name": "metadata",
                            "type": "input",
                        },
                        {
                            "name": "filtered_table",
                            "type": "output",
                        },
                        {
                            "name": "where",
                            "type": "parameter",
                            "default": None,
                        },
                        {
                            "name": "exclude_ids",
                            "type": "parameter",
                            "default": False,
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
                    "description": "Alpha diversity",
                },
            },
        }
    }


class TestIsExactMatch:
    def test_exact_match_case_sensitive(self) -> None:
        assert _is_exact_match("feature-table", ["feature-table", "diversity"])

    def test_exact_match_case_insensitive(self) -> None:
        assert _is_exact_match("FEATURE-TABLE", ["feature-table", "diversity"])
        assert _is_exact_match("feature-table", ["FEATURE-TABLE", "diversity"])

    def test_prefix_match(self) -> None:
        # Prefix matches should NOT return True for exact match only
        assert not _is_exact_match("feat", ["feature-table", "diversity"])
        assert not _is_exact_match("FEAT", ["feature-table", "diversity"])
        assert not _is_exact_match("f", ["feature-table", "diversity"])

    def test_not_a_match(self) -> None:
        assert not _is_exact_match("wrong", ["feature-table", "diversity"])
        assert not _is_exact_match("feat", ["diversity", "metadata"])

    def test_empty_candidates(self) -> None:
        assert not _is_exact_match("feature-table", [])


class TestGetCloseMatches:
    def test_returns_close_matches(self) -> None:
        candidates = ["feature-table", "feature-table", "diversity", "metadata"]
        matches = _get_close_matches("feature", candidates, limit=3)
        assert "feature-table" in matches

    def test_limits_results(self) -> None:
        candidates = ["feature-table", "feature-table", "diversity", "metadata"]
        matches = _get_close_matches("feature", candidates, limit=1)
        assert len(matches) <= 1

    def test_no_matches_below_cutoff(self) -> None:
        candidates = ["abc", "def", "xyz"]
        matches = _get_close_matches("qwerty", candidates)
        assert matches == []

    def test_empty_candidates(self) -> None:
        matches = _get_close_matches("test", [])
        assert matches == []


class TestGetSuggestions:
    def test_prefers_prefix_matches(self) -> None:
        candidates = ["feature-table", "diversity", "metadata"]
        suggestions = _get_suggestions("feat", candidates, limit=3)
        # Should return "feature-table" as a prefix match
        assert "feature-table" in suggestions

    def test_prefix_case_insensitive(self) -> None:
        candidates = ["feature-table", "diversity"]
        suggestions = _get_suggestions("FEAT", candidates, limit=3)
        assert "feature-table" in suggestions

    def test_fallback_to_difflib(self) -> None:
        candidates = ["feature-table", "diversity", "metadata"]
        suggestions = _get_suggestions("feture", candidates, limit=3)
        # Should return close matches via difflib
        assert "feature-table" in suggestions

    def test_limits_results(self) -> None:
        candidates = ["metadata", "metadata-file", "feature-table", "diversity"]
        suggestions = _get_suggestions("metad", candidates, limit=2)
        assert len(suggestions) <= 2

    def test_empty_candidates(self) -> None:
        suggestions = _get_suggestions("test", [])
        assert suggestions == []

    def test_exact_match_excluded_from_prefix_matches(self) -> None:
        candidates = ["feature-table"]
        suggestions = _get_suggestions("feature-table", candidates, limit=3)
        # Exact match should not be in suggestions
        assert suggestions == []

    def test_deduplication(self) -> None:
        # Test that duplicates are removed
        candidates = ["feature-table", "feature-table", "diversity"]
        suggestions = _get_suggestions("feat", candidates, limit=3)
        # Should not have duplicates
        assert len(suggestions) == len(set(suggestions))


class TestValidateCommand:
    def test_valid_command_no_issues(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--i-table", 30, 39),
            TokenSpan("table.qza", 40, 49),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=49)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert issues == []

    def test_typo_in_plugin(self, hierarchy_with_plugins_and_builtins: dict) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-tabel", 6, 19),  # typo: tabel instead of table
            TokenSpan("summarize", 20, 29),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=29)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert len(issues) == 1
        assert "feature-tabel" in issues[0].message
        assert "Did you mean" in issues[0].message
        assert issues[0].start == 6
        assert issues[0].end == 19

    def test_typo_in_builtin(self, hierarchy_with_plugins_and_builtins: dict) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("inof", 6, 10),  # typo: inof instead of info
            TokenSpan("refresh-cache", 11, 25),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=25)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert len(issues) == 1
        assert "inof" in issues[0].message
        assert "Did you mean" in issues[0].message

    def test_typo_in_action(self, hierarchy_with_plugins_and_builtins: dict) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summerize", 20, 29),  # typo: summerize instead of summarize
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=29)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert len(issues) == 1
        assert "summerize" in issues[0].message
        assert "feature-table" in issues[0].message  # mentions the plugin
        assert "Did you mean" in issues[0].message

    def test_multiple_issues(self, hierarchy_with_plugins_and_builtins: dict) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feat-tabel", 6, 17),  # typo in plugin
            TokenSpan("sumerize", 18, 27),  # typo in action
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=27)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        # Only 1 issue because token1 is invalid - we don't validate token2
        # to avoid noise since action candidates are unknown
        assert len(issues) == 1
        assert "feat-tabel" in issues[0].message

    def test_prefix_no_issue(self, hierarchy_with_plugins_and_builtins: dict) -> None:
        # If token is a prefix, issue should be raised (no longer suppressing prefix matches)
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feat", 6, 10),  # prefix of "feature-table"
            TokenSpan("sum", 11, 14),  # prefix of "summarize"
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=14)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        # Should have issues for both prefix tokens
        assert len(issues) == 2
        assert "feat" in issues[0].message
        assert "sum" in issues[1].message
        assert "Did you mean" in issues[0].message
        assert "Did you mean" in issues[1].message

    def test_case_insensitive_prefix_no_issue(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # Case-insensitive prefix matching should now emit issues (no longer suppressing)
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("FEAT", 6, 10),  # prefix (uppercase) of "feature-table"
            TokenSpan("Sum", 11, 14),  # prefix (capitalized) of "summarize"
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=14)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        # Should have issues for both prefix tokens
        assert len(issues) == 2
        assert "FEAT" in issues[0].message
        assert "Sum" in issues[1].message
        assert "Did you mean" in issues[0].message
        assert "Did you mean" in issues[1].message

    def test_plugin_action_prefix_emits_issue(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # Plugin action prefix should emit issue with suggestion
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("metadata", 6, 14),
            TokenSpan("tabul", 15, 20),  # prefix of "tabulate"
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=20)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert len(issues) == 1
        assert "tabul" in issues[0].message
        assert "'tabulate'" in issues[0].message
        assert issues[0].code == "q2lsp-dni/unknown-action"

    def test_insufficient_tokens_no_validation(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # Commands with less than 3 tokens should not be validated
        tokens = [TokenSpan("qiime", 0, 5)]
        cmd = ParsedCommand(tokens=tokens, start=0, end=5)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert issues == []

    def test_unknown_plugin_with_no_suggestions(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # A completely unknown name should not have suggestions
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("xyz123", 6, 12),  # completely unknown
            TokenSpan("summarize", 13, 22),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=22)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert len(issues) == 1
        assert "xyz123" in issues[0].message
        # No "Did you mean" because there are no close matches
        assert "Did you mean" not in issues[0].message

    def test_unknown_action_with_no_suggestions(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # A completely unknown action should not have suggestions
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("xyz123", 20, 26),  # completely unknown
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=26)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert len(issues) == 1
        assert "xyz123" in issues[0].message
        # No "Did you mean" because there are no close matches
        assert "Did you mean" not in issues[0].message

    def test_token1_only_command_produces_issue(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # Token1-only command with typo should produce one issue
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("toolss", 6, 12),  # typo: should be "tools"
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=12)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert len(issues) == 1
        assert "toolss" in issues[0].message
        assert issues[0].start == 6
        assert issues[0].end == 12

    def test_option_like_tokens_suppress_diagnostics(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # Options starting with - should suppress diagnostics
        # Test: qiime --help
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("--help", 6, 12),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=12)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert issues == []

        # Test: qiime tools --help
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("tools", 6, 11),
            TokenSpan("--help", 12, 18),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=18)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert issues == []

        # Test: qiime tools -h
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("tools", 6, 11),
            TokenSpan("-h", 12, 14),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=14)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert issues == []

    def test_builtin_leaf_no_subcommands(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # Builtins with no subcommands (leaf nodes) should not validate token2
        # "info" is a builtin with no subcommands
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("info", 6, 10),
            TokenSpan("something", 11, 20),  # should not be validated
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=20)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        # Only one issue possible for token1, but "info" is valid so no issues
        assert issues == []

    def test_builtin_leaf_with_typo(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # Builtin with typo in token1 should produce issue
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("inof", 6, 10),  # typo for "info"
            TokenSpan("something", 11, 20),  # should not be validated
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=20)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert len(issues) == 1
        assert "inof" in issues[0].message
        assert issues[0].start == 6
        assert issues[0].end == 10


class TestValidateOptions:
    """Tests for option validation."""

    def test_option_typo_with_suggestion(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # Test: qiime feature-table summarize --i-tabel
        # Should emit one option issue with suggestion --i-table
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--i-tabel", 30, 39),  # typo: tabel instead of table
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=39)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert len(issues) == 1
        assert "--i-tabel" in issues[0].message
        assert "Did you mean" in issues[0].message
        assert "'--i-table'" in issues[0].message
        assert issues[0].code == "q2lsp-dni/unknown-option"
        assert issues[0].start == 30
        assert issues[0].end == 39

    def test_option_prefix_suppresses_issue(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # Test: qiime feature-table summarize --i-ta
        # Should emit issue (no longer suppressing prefix matches)
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--i-ta", 30, 36),  # prefix of --i-table
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=36)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert len(issues) == 1
        assert "--i-ta" in issues[0].message
        assert "Did you mean" in issues[0].message
        assert "'--i-table'" in issues[0].message
        assert issues[0].code == "q2lsp-dni/unknown-option"

    def test_option_with_value_valid(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # Test: qiime feature-table summarize --i-table=foo
        # Should emit no issue
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--i-table=foo", 30, 43),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=43)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert issues == []


class TestValidateRequiredOptions:
    def test_plugin_action_without_signature_type_detects_required(self) -> None:
        """Plugin action params using 'type' field (not 'signature_type') are detected as required."""
        hierarchy = {
            "qiime": {
                "name": "qiime",
                "builtins": [],
                "metadata": {
                    "name": "metadata",
                    "tabulate": {
                        "name": "tabulate",
                        "signature": [
                            {
                                "name": "input",
                                "type": "parameter",
                                "description": "The metadata to tabulate.",
                            },
                            {
                                "name": "page_size",
                                "type": "parameter",
                                "description": "Page size",
                                "default": 100,
                            },
                        ],
                    },
                },
            }
        }
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("metadata", 6, 14),
            TokenSpan("tabulate", 15, 23),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=23)
        issues = validate_command(cmd, hierarchy)

        missing = [
            issue
            for issue in issues
            if issue.code == "q2lsp-dni/missing-required-option"
        ]
        assert len(missing) == 1
        assert "--p-input" in missing[0].message

    def test_missing_required_option_emits_diagnostic(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--p-obs-metadata", 30, 46),
            TokenSpan("foo", 47, 50),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=50)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)

        assert len(issues) == 1
        assert issues[0].code == "q2lsp-dni/missing-required-option"
        assert "--i-table" in issues[0].message
        assert issues[0].start == 20
        assert issues[0].end == 29

    def test_all_required_options_present_no_diagnostic(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--i-table", 30, 39),
            TokenSpan("table.qza", 40, 49),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=49)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)

        assert issues == []

    def test_only_optional_missing_no_diagnostic(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--i-table", 30, 39),
            TokenSpan("table.qza", 40, 49),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=49)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)

        assert issues == []

    def test_help_flag_suppresses_required_check(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--help", 30, 36),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=36)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)

        assert issues == []

    def test_short_help_flag_suppresses_required_check(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("-h", 30, 32),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=32)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)

        assert issues == []

    def test_help_equals_value_suppresses_required_check(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--help=1", 30, 38),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=38)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)

        assert issues == []

    def test_option_equals_value_counts_as_present(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--i-table=table.qza", 30, 49),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=49)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)

        assert issues == []

    def test_unknown_option_with_same_param_name_suppresses_missing_required(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--table", 30, 37),
            TokenSpan("table.qza", 38, 47),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=47)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)

        unknown_option_issues = [
            issue for issue in issues if issue.code == "q2lsp-dni/unknown-option"
        ]
        missing_required_issues = [
            issue
            for issue in issues
            if issue.code == "q2lsp-dni/missing-required-option"
        ]

        assert len(unknown_option_issues) == 1
        assert "--table" in unknown_option_issues[0].message
        assert missing_required_issues == []

    def test_case_insensitive_option_satisfies_required(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--I-TABLE", 30, 39),
            TokenSpan("table.qza", 40, 49),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=49)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)

        assert issues == []

    def test_builtin_required_option_missing_emits_diagnostic(self) -> None:
        """Builtin command with required=True param emits missing-required diagnostic."""
        hierarchy = {
            "qiime": {
                "name": "qiime",
                "builtins": ["tools"],
                "tools": {
                    "name": "tools",
                    "type": "builtin",
                    "import": {
                        "name": "import",
                        "type": "builtin_action",
                        "signature": [
                            {
                                "name": "input_path",
                                "type": "path",
                                "description": "Input",
                                "required": True,
                            },
                            {
                                "name": "output_path",
                                "type": "path",
                                "description": "Output",
                                "required": True,
                            },
                            {
                                "name": "format",
                                "type": "text",
                                "description": "Format",
                                "default": "auto",
                            },
                        ],
                    },
                },
            }
        }
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("tools", 6, 11),
            TokenSpan("import", 12, 18),
            TokenSpan("--format", 19, 27),
            TokenSpan("csv", 28, 31),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=31)
        issues = validate_command(cmd, hierarchy)

        missing = [
            issue
            for issue in issues
            if issue.code == "q2lsp-dni/missing-required-option"
        ]
        assert len(missing) == 2
        missing_messages = {issue.message for issue in missing}
        assert any("--input-path" in message for message in missing_messages)
        assert any("--output-path" in message for message in missing_messages)

    def test_builtin_optional_none_default_no_false_positive(self) -> None:
        """Builtin param without required flag and no default key is NOT treated as required."""
        hierarchy = {
            "qiime": {
                "name": "qiime",
                "builtins": ["tools"],
                "tools": {
                    "name": "tools",
                    "type": "builtin",
                    "import": {
                        "name": "import",
                        "type": "builtin_action",
                        "signature": [
                            {
                                "name": "verbose",
                                "type": "boolean",
                                "description": "Verbose",
                            }
                        ],
                    },
                },
            }
        }
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("tools", 6, 11),
            TokenSpan("import", 12, 18),
            TokenSpan("--verbose", 19, 28),
            TokenSpan("true", 29, 33),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=33)
        issues = validate_command(cmd, hierarchy)

        missing = [
            issue
            for issue in issues
            if issue.code == "q2lsp-dni/missing-required-option"
        ]
        assert missing == []

    def test_explicit_required_false_overrides_fallback(self) -> None:
        """Param with explicit required=False is not required even if signature_type present and no default."""
        hierarchy = {
            "qiime": {
                "name": "qiime",
                "builtins": [],
                "example-plugin": {
                    "name": "example-plugin",
                    "example-action": {
                        "name": "example-action",
                        "signature": [
                            {
                                "name": "table",
                                "type": "FeatureTable",
                                "signature_type": "input",
                                "required": False,
                            }
                        ],
                    },
                },
            }
        }
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("example-plugin", 6, 20),
            TokenSpan("example-action", 21, 35),
            TokenSpan("--p-verbose", 36, 47),
            TokenSpan("true", 48, 52),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=52)
        issues = validate_command(cmd, hierarchy)

        missing = [
            issue
            for issue in issues
            if issue.code == "q2lsp-dni/missing-required-option"
        ]
        assert missing == []

    def test_builtin_with_signature_type_uses_fallback_heuristic(self) -> None:
        hierarchy = {
            "qiime": {
                "name": "qiime",
                "builtins": ["metadata"],
                "metadata": {
                    "name": "metadata",
                    "type": "builtin",
                    "tabulate": {
                        "name": "tabulate",
                        "type": "builtin_action",
                        "signature": [
                            {
                                "name": "metadata",
                                "type": "Metadata",
                                "signature_type": "input",
                            },
                            {
                                "name": "output_path",
                                "type": "FilePath",
                                "signature_type": "parameter",
                            },
                        ],
                    },
                },
            }
        }
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("metadata", 6, 14),
            TokenSpan("tabulate", 15, 23),
            TokenSpan("--i-metadata", 24, 36),
            TokenSpan("foo", 37, 40),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=40)
        issues = validate_command(cmd, hierarchy)

        missing = [
            issue
            for issue in issues
            if issue.code == "q2lsp-dni/missing-required-option"
        ]
        assert len(missing) == 1
        assert "--p-output-path" in missing[0].message

    def test_multiple_missing_required_options(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("filter-samples", 20, 34),
            TokenSpan("--p-where", 35, 44),
            TokenSpan("some condition", 45, 59),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=59)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)

        required_issues = [
            issue
            for issue in issues
            if issue.code == "q2lsp-dni/missing-required-option"
        ]
        assert len(required_issues) == 3

    def test_cascade_typo_suppresses_missing_required(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--i-tabel", 30, 39),
            TokenSpan("table.qza", 40, 49),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=49)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)

        unknown_option_issues = [
            issue for issue in issues if issue.code == "q2lsp-dni/unknown-option"
        ]
        missing_required_issues = [
            issue
            for issue in issues
            if issue.code == "q2lsp-dni/missing-required-option"
        ]

        assert len(unknown_option_issues) == 1
        assert missing_required_issues == []

    def test_param_without_signature_type_not_treated_as_required(self) -> None:
        hierarchy = {
            "qiime": {
                "name": "qiime",
                "short_help": "QIIME 2 CLI",
                "builtins": [],
                "example-plugin": {
                    "id": "example-plugin",
                    "name": "example-plugin",
                    "example-action": {
                        "id": "example-action",
                        "name": "example-action",
                        "signature": [
                            {
                                "name": "foo",
                                "type": "Str",
                            }
                        ],
                    },
                },
            }
        }

        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("example-plugin", 6, 20),
            TokenSpan("example-action", 21, 35),
            TokenSpan("--p-foo", 36, 43),
            TokenSpan("bar", 44, 47),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=47)
        issues = validate_command(cmd, hierarchy)

        missing_required_issues = [
            issue
            for issue in issues
            if issue.code == "q2lsp-dni/missing-required-option"
        ]
        assert missing_required_issues == []

    def test_unknown_option_when_action_invalid_no_option_diagnostic(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # Unknown option when action invalid should not emit option diagnostic (only action)
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summerize", 20, 29),  # typo for summarize
            TokenSpan("--i-tabel", 30, 39),  # typo for --i-table
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=39)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        # Only action issue, no option issue because action is invalid
        assert len(issues) == 1
        assert "summerize" in issues[0].message
        assert issues[0].code != "q2lsp-dni/unknown-option"

    def test_help_option_always_valid(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # --help and -h should always be treated as valid
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--help", 30, 36),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=36)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert issues == []

        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("-h", 30, 32),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=32)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert issues == []

    def test_multiple_options_with_one_typo(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # Test with multiple options, one valid and one typo (prefix case)
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("metadata", 6, 14),
            TokenSpan("tabulate", 15, 24),
            TokenSpan("--i-metadata", 25, 38),  # valid
            TokenSpan("--i-metadat", 39, 50),  # typo (prefix of --i-metadata)
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=50)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)

        unknown_option_issues = [
            issue for issue in issues if issue.code == "q2lsp-dni/unknown-option"
        ]
        missing_required_issues = [
            issue
            for issue in issues
            if issue.code == "q2lsp-dni/missing-required-option"
        ]
        assert len(unknown_option_issues) == 1
        assert "--i-metadat" in unknown_option_issues[0].message
        assert "Did you mean" in unknown_option_issues[0].message
        assert "'--i-metadata'" in unknown_option_issues[0].message
        assert len(missing_required_issues) == 1
        assert "--p-output-path" in missing_required_issues[0].message

    def test_valid_options_no_issues(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # All valid options should produce no issues
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("filter-samples", 20, 34),
            TokenSpan("--i-table", 35, 44),
            TokenSpan("--i-metadata", 45, 58),
            TokenSpan("--o-filtered-table", 59, 76),
            TokenSpan("filtered.qza", 77, 89),
            TokenSpan("--p-where", 90, 99),
            TokenSpan("--p-exclude-ids", 100, 114),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=114)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert issues == []

    def test_case_insensitive_prefix_for_options(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # Case-insensitive prefix matching should now emit issue for options
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--I-TA", 30, 36),  # prefix (uppercase) of --i-table
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=36)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert len(issues) == 1
        assert "--I-TA" in issues[0].message
        assert "Did you mean" in issues[0].message
        assert "'--i-table'" in issues[0].message
        assert issues[0].code == "q2lsp-dni/unknown-option"

    def test_option_typo_without_suggestions(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # Completely unknown option should not have suggestions
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--i-table", 30, 39),
            TokenSpan("table.qza", 40, 49),
            TokenSpan("--xyz123", 50, 58),
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=58)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert len(issues) == 1
        assert "--xyz123" in issues[0].message
        # No "Did you mean" because there are no close matches
        assert "Did you mean" not in issues[0].message

    def test_non_option_tokens_ignored(
        self, hierarchy_with_plugins_and_builtins: dict
    ) -> None:
        # Non-option tokens (values, etc.) should be ignored
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan("feature-table", 6, 19),
            TokenSpan("summarize", 20, 29),
            TokenSpan("--i-table", 30, 39),
            TokenSpan("table.qza", 40, 50),  # value, not an option
            TokenSpan("--p-obs-metadata", 51, 67),
            TokenSpan("metadata.tsv", 68, 80),  # value, not an option
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=80)
        issues = validate_command(cmd, hierarchy_with_plugins_and_builtins)
        assert issues == []
