"""Unit tests for command_hierarchy helper functions."""

from __future__ import annotations

import click
from typing import cast

from q2lsp.qiime.command_hierarchy import (
    _click_option_to_signature_param,
    _extract_signature_from_click_command,
    _normalize_param_name,
    _option_default,
    _option_type_name,
)


class TestNormalizeParamName:
    """Tests for _normalize_param_name function."""

    def test_hyphen_to_underscore(self) -> None:
        """Hyphens are replaced with underscores."""
        assert _normalize_param_name("input-path") == "input_path"

    def test_multiple_hyphens(self) -> None:
        """Multiple hyphens are replaced."""
        assert _normalize_param_name("my-input-path") == "my_input_path"

    def test_single_word(self) -> None:
        """Single word remains unchanged."""
        assert _normalize_param_name("table") == "table"

    def test_unchanged_no_hyphens(self) -> None:
        """String without hyphens remains unchanged."""
        assert _normalize_param_name("input_path") == "input_path"

    def test_none_returns_empty_string(self) -> None:
        """None returns empty string."""
        assert _normalize_param_name(None) == ""

    def test_empty_string(self) -> None:
        """Empty string returns empty string."""
        assert _normalize_param_name("") == ""

    def test_leading_hyphen(self) -> None:
        """Leading hyphen is replaced."""
        assert _normalize_param_name("-input") == "_input"

    def test_trailing_hyphen(self) -> None:
        """Trailing hyphen is replaced."""
        assert _normalize_param_name("input-") == "input_"


class TestOptionDefault:
    """Tests for _option_default function."""

    def test_required_returns_none(self) -> None:
        """Required option returns None."""
        opt = click.Option(["--input"], required=True)
        assert _option_default(opt) is None

    def test_callable_default_returns_none(self) -> None:
        """Callable default returns None."""

        def mock_default() -> str:
            return "default"

        opt = click.Option(["--input"], default=mock_default)
        assert _option_default(opt) is None

    def test_lambda_default_returns_none(self) -> None:
        """Lambda default returns None."""
        opt = click.Option(["--input"], default=lambda: "default")
        assert _option_default(opt) is None

    def test_string_default_passthrough(self) -> None:
        """String default is passed through."""
        opt = click.Option(["--input"], default="default_value")
        assert _option_default(opt) == "default_value"

    def test_int_default_passthrough(self) -> None:
        """Integer default is passed through."""
        opt = click.Option(["--input"], default=42)
        assert _option_default(opt) == 42

    def test_float_default_passthrough(self) -> None:
        """Float default is passed through."""
        opt = click.Option(["--input"], default=3.14)
        assert _option_default(opt) == 3.14

    def test_list_default_passthrough(self) -> None:
        """List default is passed through."""
        opt = click.Option(["--input"], default=["a", "b"])
        assert _option_default(opt) == ["a", "b"]

    def test_none_default_passthrough(self) -> None:
        """None default is passed through."""
        opt = click.Option(["--input"], default=None)
        assert _option_default(opt) is None

    def test_false_default_passthrough(self) -> None:
        """False default is passed through."""
        opt = click.Option(["--input"], default=False)
        assert _option_default(opt) is False

    def test_zero_default_passthrough(self) -> None:
        """Zero default is passed through."""
        opt = click.Option(["--input"], default=0)
        assert _option_default(opt) == 0

    def test_empty_string_default_passthrough(self) -> None:
        """Empty string default is passed through."""
        opt = click.Option(["--input"], default="")
        assert _option_default(opt) == ""


class TestOptionTypeName:
    """Tests for _option_type_name function."""

    def test_named_click_type(self) -> None:
        """Returns name from named click type."""
        opt = click.Option(["--input"], type=click.STRING)
        assert _option_type_name(opt) == "text"

    def test_path_type(self) -> None:
        """Returns name from Path type."""
        opt = click.Option(["--input"], type=click.Path())
        assert _option_type_name(opt) == "path"

    def test_int_type(self) -> None:
        """Returns name from Int type."""
        opt = click.Option(["--input"], type=click.INT)
        assert _option_type_name(opt) == "integer"

    def test_float_type(self) -> None:
        """Returns name from Float type."""
        opt = click.Option(["--input"], type=click.FLOAT)
        assert _option_type_name(opt) == "float"

    def test_bool_type(self) -> None:
        """Returns name from Bool type."""
        opt = click.Option(["--input"], type=click.BOOL)
        assert _option_type_name(opt) == "boolean"

    def test_choice_type(self) -> None:
        """Returns name from Choice type."""
        opt = click.Option(["--input"], type=click.Choice(["a", "b"]))
        assert _option_type_name(opt) == "choice"

    def test_custom_type_without_name(self) -> None:
        """Returns class name for custom type without name."""

        class CustomType(click.ParamType):
            pass

        opt = click.Option(["--input"], type=CustomType())
        assert _option_type_name(opt) == "CustomType"


class TestClickOptionToSignatureParam:
    """Tests for _click_option_to_signature_param function."""

    def test_basic_option(self) -> None:
        """Basic option with name, type, and description."""
        opt = click.Option(["--input"], type=click.STRING, help="Input file")
        result = _click_option_to_signature_param(opt)
        assert result["name"] == "input"
        assert result["type"] == "text"
        assert result["description"] == "Input file"

    def test_option_with_default(self) -> None:
        """Option includes default value."""
        opt = click.Option(["--input"], default="value")
        result = _click_option_to_signature_param(opt)
        assert result.get("default") == "value"

    def test_option_with_metavar(self) -> None:
        """Option includes metavar."""
        opt = click.Option(["--input"], metavar="PATH")
        result = _click_option_to_signature_param(opt)
        assert result.get("metavar") == "PATH"

    def test_option_with_multiple(self) -> None:
        """Option includes multiple flag."""
        opt = click.Option(["--input"], multiple=True)
        result = _click_option_to_signature_param(opt)
        assert result.get("multiple") == str(True)

    def test_option_is_bool_flag(self) -> None:
        """Option includes is_bool_flag."""
        opt = click.Option(["--input/--no-input"], is_flag=True)
        result = _click_option_to_signature_param(opt)
        assert result.get("is_bool_flag") is True

    def test_required_option_omits_default(self) -> None:
        """Required option doesn't include default."""
        opt = click.Option(["--input"], required=True)
        result = _click_option_to_signature_param(opt)
        assert "default" not in result

    def test_callable_default_omits_default(self) -> None:
        """Callable default doesn't include default field."""
        opt = click.Option(["--input"], default=lambda: "value")
        result = _click_option_to_signature_param(opt)
        assert "default" not in result

    def test_hyphenated_name_normalized(self) -> None:
        """Option name with hyphens is normalized."""
        opt = click.Option(["--input-path"])
        result = _click_option_to_signature_param(opt)
        assert result["name"] == "input_path"

    def test_empty_description(self) -> None:
        """Option with no help has empty description."""
        opt = click.Option(["--input"])
        result = _click_option_to_signature_param(opt)
        assert result["description"] == ""

    def test_complex_option(self) -> None:
        """Option with all fields populated."""
        opt = click.Option(
            ["--input-path"],
            type=click.Path(),
            help="Input path",
            default=["default.txt"],
            metavar="PATH",
            multiple=True,
        )
        result = _click_option_to_signature_param(opt)
        assert result["name"] == "input_path"
        assert result["type"] == "path"
        assert result["description"] == "Input path"
        assert result.get("default") == ["default.txt"]
        assert result.get("metavar") == "PATH"
        assert result.get("multiple") == str(True)
        assert "is_bool_flag" not in result


class TestExtractSignatureFromClickCommand:
    """Tests for _extract_signature_from_click_command function."""

    def test_command_with_options(self) -> None:
        """Extracts options from command."""
        cmd = click.Command(
            "test",
            params=[
                click.Option(["--input"], type=click.STRING, help="Input"),
                click.Option(["--output"], type=click.Path()),
            ],
        )
        result = _extract_signature_from_click_command(cmd)
        assert len(result) == 2
        assert result[0]["name"] == "input"
        assert result[1]["name"] == "output"

    def test_command_with_no_options(self) -> None:
        """Empty list for command with no options."""
        cmd = click.Command("test", params=[])
        result = _extract_signature_from_click_command(cmd)
        assert result == []

    def test_hidden_options_skipped(self) -> None:
        """Hidden options are not included."""
        opt1 = click.Option(["--input"], help="Input")
        opt2 = click.Option(["--secret"], help="Secret")
        opt2.hidden = True
        cmd = click.Command("test", params=[opt1, opt2])
        result = _extract_signature_from_click_command(cmd)
        assert len(result) == 1
        assert result[0]["name"] == "input"

    def test_arguments_skipped(self) -> None:
        """Arguments (non-Options) are skipped."""
        opt = click.Option(["--input"], help="Input")
        arg = click.Argument(["output"])
        cmd = click.Command("test", params=[opt, arg])
        result = _extract_signature_from_click_command(cmd)
        assert len(result) == 1
        assert result[0]["name"] == "input"

    def test_visible_only_options(self) -> None:
        """Only visible Option parameters are included."""
        opt1 = click.Option(["--input"], help="Input")
        opt2 = click.Option(["--output"], help="Output")
        opt3 = click.Option(["--hidden"], help="Hidden")
        opt3.hidden = True
        cmd = click.Command("test", params=[opt1, opt2, opt3])
        result = _extract_signature_from_click_command(cmd)
        names = {entry["name"] for entry in result}
        assert names == {"input", "output"}

    def test_command_without_params_attribute(self) -> None:
        """Handles command without params attribute."""
        result = _extract_signature_from_click_command(
            cast(click.BaseCommand, object())
        )
        assert result == []
