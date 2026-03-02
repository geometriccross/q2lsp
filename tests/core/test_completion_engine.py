"""Tests for core completion engine."""

from __future__ import annotations

from q2lsp.core.completion_engine import get_completions
from q2lsp.core.types import (
    ActionCandidate,
    CommandCandidate,
    CompletionData,
    CompletionItem,
    COMPLETION_KIND_ACTION,
    COMPLETION_KIND_BUILTIN,
    COMPLETION_KIND_PARAMETER,
    COMPLETION_KIND_PLUGIN,
    COMPLETION_MODE_PARAMETER,
    COMPLETION_MODE_ROOT,
    CompletionQuery,
    ParameterCandidate,
)


def test_root_completion_returns_plugins_and_builtins() -> None:
    data = CompletionData(
        root_items=(
            CompletionItem(
                label="info",
                detail="Display information",
                kind=COMPLETION_KIND_BUILTIN,
            ),
            CompletionItem(
                label="feature-table",
                detail="Feature table operations",
                kind=COMPLETION_KIND_PLUGIN,
            ),
        )
    )
    query = CompletionQuery(mode=COMPLETION_MODE_ROOT, prefix="")

    items = get_completions(query, data)

    labels = {item.label for item in items}
    assert labels == {"info", "feature-table"}


def test_parameter_completion_excludes_used_and_keeps_help() -> None:
    summarize = ActionCandidate(
        item=CompletionItem(
            label="summarize",
            detail="Summarize a feature table",
            kind=COMPLETION_KIND_ACTION,
        ),
        parameters=(
            ParameterCandidate(
                name="table",
                item=CompletionItem(
                    label="--i-table",
                    detail="(required) [FeatureTable] Input table",
                    kind=COMPLETION_KIND_PARAMETER,
                ),
                match_texts=("--i-table", "i-table", "table", "--table"),
            ),
            ParameterCandidate(
                name="output_dir",
                item=CompletionItem(
                    label="--o-output-dir",
                    detail="[Path] Output directory",
                    kind=COMPLETION_KIND_PARAMETER,
                ),
                match_texts=(
                    "--o-output-dir",
                    "o-output-dir",
                    "output-dir",
                    "--output-dir",
                ),
            ),
        ),
    )
    data = CompletionData(
        commands=(
            CommandCandidate(
                name="feature-table",
                is_builtin=False,
                actions=(summarize,),
            ),
        )
    )
    query = CompletionQuery(
        mode=COMPLETION_MODE_PARAMETER,
        prefix="--",
        plugin_name="feature-table",
        action_name="summarize",
        used_parameters=frozenset({"table"}),
    )

    items = get_completions(query, data)

    labels = {item.label for item in items}
    assert "--i-table" not in labels
    assert "--o-output-dir" in labels
    assert "--help" in labels
