"""Tests for get completions usecase."""

from __future__ import annotations

import pytest

from q2lsp.usecases.get_completions_usecase import CompletionRequest, get_completions


def test_usecase_connects_adapter_and_core_engine() -> None:
    hierarchy = {
        "qiime": {
            "builtins": ["info"],
            "info": {"short_help": "Display information"},
            "feature-table": {
                "short_description": "Feature table operations",
            },
        }
    }
    request = CompletionRequest(
        mode="root",
        prefix="f",
        command_tokens=("qiime",),
    )

    items = get_completions(request, hierarchy)

    assert [item.label for item in items] == ["feature-table"]


@pytest.mark.parametrize(
    ("req", "expected_labels"),
    [
        (
            CompletionRequest(
                mode="root",
                prefix="",
                command_tokens=("qiime",),
            ),
            ["info", "feature-table"],
        ),
        (
            CompletionRequest(
                mode="plugin",
                prefix="",
                command_tokens=("qiime", "feature-table"),
            ),
            ["summarize"],
        ),
        (
            CompletionRequest(
                mode="parameter",
                prefix="--",
                command_tokens=(
                    "qiime",
                    "feature-table",
                    "summarize",
                    "--i-table",
                ),
            ),
            ["--o-output-dir", "--help"],
        ),
        (
            CompletionRequest(
                mode="parameter",
                prefix="table",
                command_tokens=("qiime", "feature-table", "summarize"),
            ),
            ["--i-table"],
        ),
        (
            CompletionRequest(
                mode="parameter",
                prefix="i-table",
                command_tokens=("qiime", "feature-table", "summarize"),
            ),
            [],
        ),
    ],
)
def test_usecase_completion_baseline(
    req: CompletionRequest,
    expected_labels: list[str],
) -> None:
    hierarchy = {
        "qiime": {
            "builtins": ["info"],
            "info": {
                "short_help": "Display information",
            },
            "feature-table": {
                "short_description": "Feature table operations",
                "summarize": {
                    "description": "Summarize a feature table",
                    "signature": [
                        {
                            "name": "table",
                            "type": "FeatureTable",
                            "description": "Input table",
                            "signature_type": "input",
                        },
                        {
                            "name": "output_dir",
                            "type": "Path",
                            "description": "Output directory",
                            "default": None,
                            "signature_type": "output",
                        },
                    ],
                },
            },
        }
    }

    items = get_completions(req, hierarchy)

    assert [item.label for item in items] == expected_labels
