"""Tests for QIIME option token helper functions."""

from __future__ import annotations

from q2lsp.qiime.option_tokens import (
    normalize_option_to_param_name,
    option_label_matches_prefix,
)


def test_normalize_option_to_param_name_standard_option() -> None:
    assert normalize_option_to_param_name("--i-table") == "table"


class TestNormalizeOptionToParamName:
    def test_option_with_value(self) -> None:
        assert (
            normalize_option_to_param_name("--p-sampling-depth=100") == "sampling_depth"
        )

    def test_non_option(self) -> None:
        assert normalize_option_to_param_name("value.qza") is None

    def test_single_dash(self) -> None:
        assert normalize_option_to_param_name("-h") is None

    def test_no_prefix(self) -> None:
        """Option without QIIME prefix (e.g., --verbose)."""
        assert normalize_option_to_param_name("--verbose") == "verbose"

    def test_output_prefix(self) -> None:
        assert normalize_option_to_param_name("--o-visualization") == "visualization"

    def test_metadata_prefix(self) -> None:
        assert normalize_option_to_param_name("--m-metadata-file") == "metadata_file"

    def test_parameter_prefix(self) -> None:
        assert normalize_option_to_param_name("--p-n-jobs") == "n_jobs"

    def test_help_option(self) -> None:
        assert normalize_option_to_param_name("--help") == "help"

    def test_case_insensitive_option(self) -> None:
        assert normalize_option_to_param_name("--I-TABLE") == "table"

    def test_empty_long_option_normalizes_to_empty_name(self) -> None:
        """Malformed '--' is still a long option but has no param name."""
        assert normalize_option_to_param_name("--") == ""

    def test_empty_qiime_prefixed_option_normalizes_to_empty_name(self) -> None:
        """Malformed '--i-' strips the QIIME prefix and leaves no param name."""
        assert normalize_option_to_param_name("--i-") == ""


class TestOptionLabelMatchesPrefix:
    """Tests for option_label_matches_prefix function."""

    def test_empty_prefix_returns_true(self) -> None:
        """Empty prefix always returns True."""
        assert option_label_matches_prefix("--table", "")
        assert option_label_matches_prefix("-t", "")
        assert option_label_matches_prefix("table", "")

    def test_match_with_leading_dashes(self) -> None:
        """Matches option with leading dashes."""
        assert option_label_matches_prefix("--table", "table")
        assert option_label_matches_prefix("-t", "t")

    def test_match_without_leading_dashes(self) -> None:
        """Matches option without leading dashes."""
        assert option_label_matches_prefix("table", "table")

    def test_match_with_i_prefix(self) -> None:
        """Matches option with 'i-' prefix."""
        assert option_label_matches_prefix("--i-table", "table")
        assert option_label_matches_prefix("--i-table", "ta")

    def test_match_with_o_prefix(self) -> None:
        """Matches option with 'o-' prefix."""
        assert option_label_matches_prefix("--o-results", "results")
        assert option_label_matches_prefix("--o-results", "res")

    def test_match_with_p_prefix(self) -> None:
        """Matches option with 'p-' prefix."""
        assert option_label_matches_prefix("--p-threads", "threads")
        assert option_label_matches_prefix("--p-threads", "t")

    def test_match_with_m_prefix(self) -> None:
        """Matches option with 'm-' prefix."""
        assert option_label_matches_prefix("--m-file", "file")
        assert option_label_matches_prefix("--m-file", "f")

    def test_short_form_match(self) -> None:
        """Matches short form after stripping prefix."""
        assert option_label_matches_prefix("--i-table", "t")
        assert option_label_matches_prefix("--o-results", "r")

    def test_negative_case_no_match(self) -> None:
        """Returns False when option doesn't match prefix."""
        assert not option_label_matches_prefix("--table", "results")
        assert not option_label_matches_prefix("--i-table", "results")

    def test_prefix_with_leading_dash(self) -> None:
        """Handles prefix with leading dash."""
        assert option_label_matches_prefix("--table", "--table")
        assert option_label_matches_prefix("--i-table", "--t")

    def test_prefix_with_single_dash(self) -> None:
        """Handles prefix with single leading dash."""
        assert option_label_matches_prefix("-t", "-t")

    def test_mixed_case_not_matching(self) -> None:
        """Mixed case doesn't match."""
        assert not option_label_matches_prefix("--table", "TABLE")

    def test_partial_match_after_prefix(self) -> None:
        """Partial match after prefix returns True."""
        assert option_label_matches_prefix("--i-table", "tab")
        assert option_label_matches_prefix("--o-results", "res")

    def test_no_match_after_prefix(self) -> None:
        """No match after prefix returns False."""
        assert not option_label_matches_prefix("--i-table", "xyz")

    def test_single_char_option(self) -> None:
        """Handles single character options."""
        assert option_label_matches_prefix("-t", "t")
        assert option_label_matches_prefix("--i-t", "t")
