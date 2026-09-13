"""Tests for QIIME option token helper functions."""

from __future__ import annotations

import pytest

from q2lsp.qiime.option_tokens import (
    group_option_tokens,
    normalize_option_to_param_name,
)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("--i-table table.qza", [("--i-table", None, ("table.qza",))]),
        (
            "--p-where sample id --output-dir out",
            [
                ("--p-where", None, ("sample", "id")),
                ("--output-dir", None, ("out",)),
            ],
        ),
        (
            "--use-cache --verbose --help",
            [
                ("--use-cache", None, ()),
                ("--verbose", None, ()),
                ("--help", None, ()),
            ],
        ),
        (
            "--i-table=table.qza --verbose",
            [
                ("--i-table", "table.qza", ()),
                ("--verbose", None, ()),
            ],
        ),
        (
            "--p-obs-metadata -h --i-table table.qza",
            [
                ("--p-obs-metadata", None, ("-h",)),
                ("--i-table", None, ("table.qza",)),
            ],
        ),
    ],
)
def test_group_options(
    source: str, expected: list[tuple[str, str | None, tuple[str, ...]]]
) -> None:
    tokens = ["qiime", "feature-table", "summarize", *source.split()]
    groups = group_option_tokens(tokens, str, start_index=3)
    assert [
        (group.option_text, group.inline_value, group.value_tokens) for group in groups
    ] == expected


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
