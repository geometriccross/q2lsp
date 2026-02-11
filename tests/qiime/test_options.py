"""Tests for options helper functions."""

from __future__ import annotations

from q2lsp.qiime.options import (
    format_qiime_option_label,
    option_label_matches_prefix,
    param_is_required,
    qiime_option_prefix,
    qiime_signature_kind,
)
from q2lsp.qiime.types import JsonObject


class TestQiimeOptionPrefix:
    """Tests for qiime_option_prefix function."""

    def test_input_type(self) -> None:
        """Input type returns 'i' prefix."""
        param: JsonObject = {"type": "input"}
        assert qiime_option_prefix(param) == "i"

    def test_output_type(self) -> None:
        """Output type returns 'o' prefix."""
        param: JsonObject = {"type": "output"}
        assert qiime_option_prefix(param) == "o"

    def test_parameter_type(self) -> None:
        """Parameter type returns 'p' prefix."""
        param: JsonObject = {"type": "parameter"}
        assert qiime_option_prefix(param) == "p"

    def test_metadata_type(self) -> None:
        """Metadata type returns 'm' prefix."""
        param: JsonObject = {"type": "metadata"}
        assert qiime_option_prefix(param) == "m"

    def test_signature_type_input(self) -> None:
        """Signature type 'input' returns 'i' prefix."""
        param: JsonObject = {"signature_type": "input"}
        assert qiime_option_prefix(param) == "i"

    def test_signature_type_output(self) -> None:
        """Signature type 'output' returns 'o' prefix."""
        param: JsonObject = {"signature_type": "output"}
        assert qiime_option_prefix(param) == "o"

    def test_case_insensitive(self) -> None:
        """Type matching is case-insensitive."""
        test_cases = [
            ("Input", "i"),
            ("INPUT", "i"),
            ("Output", "o"),
            ("OUTPUT", "o"),
            ("Parameter", "p"),
            ("PARAMETER", "p"),
            ("Metadata", "m"),
            ("METADATA", "m"),
        ]
        for type_val, expected_prefix in test_cases:
            param: JsonObject = {"type": type_val}
            assert qiime_option_prefix(param) == expected_prefix

    def test_partial_match(self) -> None:
        """Partial match works for signature_type field."""
        param: JsonObject = {"signature_type": "input_data"}
        assert qiime_option_prefix(param) == "i"

    def test_unknown_type(self) -> None:
        """Unknown type returns empty prefix."""
        param: JsonObject = {"type": "unknown"}
        assert qiime_option_prefix(param) == ""

    def test_none_type(self) -> None:
        """None type returns empty prefix."""
        param: JsonObject = {"type": None}
        assert qiime_option_prefix(param) == ""

    def test_missing_type_fields(self) -> None:
        """Missing type fields return empty prefix."""
        param: JsonObject = {"name": "test"}
        assert qiime_option_prefix(param) == ""

    def test_empty_dict(self) -> None:
        """Empty dict returns empty prefix."""
        param: JsonObject = {}
        assert qiime_option_prefix(param) == ""

    def test_signature_type_precedence(self) -> None:
        """signature_type takes precedence over type."""
        param: JsonObject = {"type": "output", "signature_type": "input"}
        assert qiime_option_prefix(param) == "i"


class TestFormatQiimeOptionLabel:
    """Tests for format_qiime_option_label function."""

    def test_with_prefix(self) -> None:
        """Label with prefix."""
        assert format_qiime_option_label("i", "table") == "--i-table"

    def test_with_o_prefix(self) -> None:
        """Label with output prefix."""
        assert format_qiime_option_label("o", "results") == "--o-results"

    def test_with_p_prefix(self) -> None:
        """Label with parameter prefix."""
        assert format_qiime_option_label("p", "threads") == "--p-threads"

    def test_with_m_prefix(self) -> None:
        """Label with metadata prefix."""
        assert format_qiime_option_label("m", "file") == "--m-file"

    def test_without_prefix(self) -> None:
        """Label without prefix."""
        assert format_qiime_option_label("", "table") == "--table"

    def test_underscores_to_dashes(self) -> None:
        """Underscores are converted to dashes."""
        assert format_qiime_option_label("i", "input_file") == "--i-input-file"

    def test_empty_name_with_prefix(self) -> None:
        """Empty name with prefix."""
        assert format_qiime_option_label("i", "") == "--i-"

    def test_empty_name_without_prefix(self) -> None:
        """Empty name without prefix."""
        assert format_qiime_option_label("", "") == "--"

    def test_multiple_underscores(self) -> None:
        """Multiple underscores converted to dashes."""
        assert (
            format_qiime_option_label("p", "my_parameter_name")
            == "--p-my-parameter-name"
        )

    def test_single_underscore(self) -> None:
        """Single underscore converted to dash."""
        assert format_qiime_option_label("m", "input") == "--m-input"


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


class TestParamIsRequired:
    """Tests for param_is_required function."""

    def test_explicit_required_true(self) -> None:
        """Explicit required=True returns True."""
        param: JsonObject = {"required": True}
        assert param_is_required(param)

    def test_explicit_required_false(self) -> None:
        """Explicit required=False returns False."""
        param: JsonObject = {"required": False}
        assert not param_is_required(param)

    def test_explicit_required_true_with_default(self) -> None:
        """Explicit required flag takes precedence over default."""
        param: JsonObject = {"required": True, "default": "foo"}
        assert param_is_required(param)

    def test_explicit_required_false_with_signature_type(self) -> None:
        """Explicit required flag takes precedence over signature_type heuristic."""
        param: JsonObject = {"required": False, "signature_type": "input"}
        assert not param_is_required(param)

    def test_fallback_signature_type_no_default(self) -> None:
        """Fallback heuristic returns True when signature_type exists and default absent."""
        param: JsonObject = {"signature_type": "input"}
        assert param_is_required(param)

    def test_fallback_signature_type_with_default(self) -> None:
        """Fallback heuristic returns False when default key is present."""
        param: JsonObject = {"signature_type": "input", "default": None}
        assert not param_is_required(param)

    def test_fallback_type_field_no_default(self) -> None:
        """type field with SDK kind and no default is required."""
        param: JsonObject = {"name": "input", "type": "parameter"}
        assert param_is_required(param)

    def test_fallback_type_field_click_native_not_required(self) -> None:
        """type field with click-native value is not required even without default."""
        param: JsonObject = {"name": "verbose", "type": "text"}
        assert not param_is_required(param)

    def test_no_flags_returns_false(self) -> None:
        """Missing required and signature_type returns False."""
        param: JsonObject = {"name": "verbose", "type": "boolean"}
        assert not param_is_required(param)

    def test_empty_dict_returns_false(self) -> None:
        """Empty parameter object returns False."""
        param: JsonObject = {}
        assert not param_is_required(param)


class TestQiimeSignatureKind:
    """Tests for qiime_signature_kind function."""

    def test_signature_type_takes_precedence(self) -> None:
        """signature_type is preferred over type when both exist."""
        param: JsonObject = {"signature_type": "input", "type": "parameter"}
        assert qiime_signature_kind(param) == "input"

    def test_type_field_recognized_for_sdk_kinds(self) -> None:
        """Known QIIME SDK kinds in type are recognized."""
        for kind in {"input", "output", "parameter", "metadata", "artifact"}:
            param: JsonObject = {"type": kind}
            assert qiime_signature_kind(param) == kind

    def test_type_field_click_native_returns_none(self) -> None:
        """Click-native types are not treated as QIIME signature kinds."""
        assert qiime_signature_kind({"type": "text"}) is None
        assert qiime_signature_kind({"type": "path"}) is None
        assert qiime_signature_kind({"type": "boolean"}) is None

    def test_empty_dict_returns_none(self) -> None:
        """Missing signature fields returns None."""
        assert qiime_signature_kind({}) is None

    def test_case_insensitive(self) -> None:
        """Both source fields are matched case-insensitively."""
        assert qiime_signature_kind({"type": "Input"}) == "input"
        assert qiime_signature_kind({"signature_type": "OUTPUT"}) == "output"
