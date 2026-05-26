"""Tests for QIIME signature helper functions."""

from __future__ import annotations

from q2lsp.qiime.signature import (
    format_qiime_option_label,
    param_is_required,
    qiime_option_prefix,
    qiime_signature_kind,
)
from q2lsp.qiime.types import JsonObject


class TestQiimeOptionPrefix:
    """Tests for qiime_option_prefix function."""

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

    def test_signature_type_prefix_match_is_retained_for_sdk_derivatives(self) -> None:
        """signature_type values beginning with known kinds map to that prefix."""
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

    def test_unknown_signature_type_without_default_is_required(self) -> None:
        """Any signature_type currently marks a default-less param required."""
        param: JsonObject = {"signature_type": "unknown"}
        assert param_is_required(param)

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

    def test_unknown_signature_type_is_returned_lowercase(self) -> None:
        """signature_type is trusted even when it is not a known SDK kind."""
        assert qiime_signature_kind({"signature_type": "Unknown"}) == "unknown"
