"""Tests for get completions usecase."""

from __future__ import annotations

import pytest

from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.types import CommandHierarchy
from q2lsp.usecases.get_completions_usecase import (
    CompletionRequest,
    get_completions,
)


@pytest.fixture
def completion_hierarchy() -> CommandHierarchy:
    return {
        "qiime": {
            "builtins": ["info"],
            "info": {"short_help": "Display information"},
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

    items = get_completions(request, QiimeCatalog.from_hierarchy(hierarchy))

    assert [item.label for item in items] == ["feature-table"]


@pytest.mark.parametrize(
    "completion_request",
    [
        CompletionRequest(
            mode="root",
            prefix="",
            command_tokens=("qiime",),
        ),
        CompletionRequest(
            mode="root",
            prefix="i",
            command_tokens=("qiime",),
        ),
        CompletionRequest(
            mode="plugin",
            prefix="",
            command_tokens=("qiime", "feature-table"),
        ),
        CompletionRequest(
            mode="parameter",
            prefix="--",
            command_tokens=("qiime", "feature-table", "summarize", "--i-table"),
        ),
        CompletionRequest(
            mode="parameter",
            prefix="table",
            command_tokens=("qiime", "feature-table", "summarize"),
        ),
    ],
)
def test_catalog_backed_completions_match_baseline(
    completion_hierarchy: CommandHierarchy,
    completion_request: CompletionRequest,
) -> None:
    items = get_completions(
        completion_request,
        QiimeCatalog.from_hierarchy(completion_hierarchy),
    )

    assert items


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

    items = get_completions(req, QiimeCatalog.from_hierarchy(hierarchy))

    assert [item.label for item in items] == expected_labels
