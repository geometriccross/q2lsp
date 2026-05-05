"""Tests for core completion engine."""

from __future__ import annotations

from q2lsp.core.completion_engine import get_completions
from q2lsp.core.types import (
    ActionCandidate,
    CommandCandidate,
    CompletionData,
    CompletionItem,
    CompletionKind,
    CompletionMode,
    CompletionQuery,
    ParameterCandidate,
)


def test_none_completion_returns_empty_list() -> None:
    data = CompletionData(
        root_items=(
            CompletionItem(
                label="feature-table",
                detail="Feature table operations",
                kind=CompletionKind.PLUGIN,
            ),
        )
    )
    query = CompletionQuery(mode=CompletionMode.NONE, prefix="feature")

    assert get_completions(query, data) == []


def test_root_completion_returns_plugins_and_builtins() -> None:
    data = CompletionData(
        root_items=(
            CompletionItem(
                label="info",
                detail="Display information",
                kind=CompletionKind.BUILTIN,
            ),
            CompletionItem(
                label="feature-table",
                detail="Feature table operations",
                kind=CompletionKind.PLUGIN,
            ),
        )
    )
    query = CompletionQuery(mode=CompletionMode.ROOT, prefix="")

    items = get_completions(query, data)

    labels = {item.label for item in items}
    assert labels == {"info", "feature-table"}


def test_plugin_action_completion_filters_by_prefix() -> None:
    data = CompletionData(
        commands=(
            CommandCandidate(
                name="feature-table",
                is_builtin=False,
                actions=(
                    ActionCandidate(
                        item=CompletionItem(
                            label="summarize",
                            detail="Summarize a feature table",
                            kind=CompletionKind.ACTION,
                        ),
                    ),
                    ActionCandidate(
                        item=CompletionItem(
                            label="tabulate-seqs",
                            detail="Tabulate sequences",
                            kind=CompletionKind.ACTION,
                        ),
                    ),
                ),
            ),
        )
    )
    query = CompletionQuery(
        mode=CompletionMode.PLUGIN,
        prefix="sum",
        plugin_name="feature-table",
    )

    items = get_completions(query, data)

    assert {item.label for item in items} == {"summarize"}


def test_unknown_plugin_action_completion_returns_empty_list() -> None:
    data = CompletionData(
        commands=(CommandCandidate(name="feature-table", is_builtin=False),)
    )
    query = CompletionQuery(
        mode=CompletionMode.PLUGIN,
        prefix="sum",
        plugin_name="unknown-plugin",
    )

    assert get_completions(query, data) == []


def test_unknown_parameter_action_completion_returns_empty_list() -> None:
    data = CompletionData(
        commands=(CommandCandidate(name="feature-table", is_builtin=False),)
    )
    query = CompletionQuery(
        mode=CompletionMode.PARAMETER,
        prefix="--",
        plugin_name="feature-table",
        action_name="unknown-action",
    )

    assert get_completions(query, data) == []


def test_builtin_command_with_no_actions_returns_help() -> None:
    data = CompletionData(
        commands=(CommandCandidate(name="info", is_builtin=True),)
    )
    query = CompletionQuery(
        mode=CompletionMode.PLUGIN,
        prefix="--",
        plugin_name="info",
    )

    items = get_completions(query, data)

    assert {item.label for item in items} == {"--help"}


def test_non_builtin_action_with_no_parameters_returns_empty_list() -> None:
    data = CompletionData(
        commands=(
            CommandCandidate(
                name="feature-table",
                is_builtin=False,
                actions=(
                    ActionCandidate(
                        item=CompletionItem(
                            label="summarize",
                            detail="Summarize a feature table",
                            kind=CompletionKind.ACTION,
                        ),
                    ),
                ),
            ),
        )
    )
    query = CompletionQuery(
        mode=CompletionMode.PARAMETER,
        prefix="--",
        plugin_name="feature-table",
        action_name="summarize",
    )

    assert get_completions(query, data) == []


def test_parameter_completion_excludes_used_and_keeps_help() -> None:
    summarize = ActionCandidate(
        item=CompletionItem(
            label="summarize",
            detail="Summarize a feature table",
            kind=CompletionKind.ACTION,
        ),
        parameters=(
            ParameterCandidate(
                name="table",
                item=CompletionItem(
                    label="--i-table",
                    detail="(required) [FeatureTable] Input table",
                    kind=CompletionKind.PARAMETER,
                ),
                match_texts=("--i-table", "i-table", "table", "--table"),
            ),
            ParameterCandidate(
                name="output_dir",
                item=CompletionItem(
                    label="--o-output-dir",
                    detail="[Path] Output directory",
                    kind=CompletionKind.PARAMETER,
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
        mode=CompletionMode.PARAMETER,
        prefix="--",
        plugin_name="feature-table",
        action_name="summarize",
        used_parameters=frozenset({"table"}),
    )

    items = get_completions(query, data)

    assert {item.label for item in items} == {"--o-output-dir", "--help"}


def test_parameter_completion_matches_bare_prefix() -> None:
    summarize = ActionCandidate(
        item=CompletionItem(
            label="summarize",
            detail="Summarize a feature table",
            kind=CompletionKind.ACTION,
        ),
        parameters=(
            ParameterCandidate(
                name="output_dir",
                item=CompletionItem(
                    label="--o-output-dir",
                    detail="[Path] Output directory",
                    kind=CompletionKind.PARAMETER,
                ),
                match_texts=("--o-output-dir", "o-output-dir", "output-dir"),
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
        mode=CompletionMode.PARAMETER,
        prefix="output",
        plugin_name="feature-table",
        action_name="summarize",
    )

    items = get_completions(query, data)

    assert {item.label for item in items} == {"--o-output-dir"}


def test_parameter_completion_excludes_used_help() -> None:
    summarize = ActionCandidate(
        item=CompletionItem(
            label="summarize",
            detail="Summarize a feature table",
            kind=CompletionKind.ACTION,
        ),
        parameters=(
            ParameterCandidate(
                name="table",
                item=CompletionItem(
                    label="--i-table",
                    detail="(required) [FeatureTable] Input table",
                    kind=CompletionKind.PARAMETER,
                ),
                match_texts=("--i-table", "i-table", "table"),
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
        mode=CompletionMode.PARAMETER,
        prefix="--",
        plugin_name="feature-table",
        action_name="summarize",
        used_parameters=frozenset({"help"}),
    )

    items = get_completions(query, data)

    assert {item.label for item in items} == {"--i-table"}
