"""Regression tests for completion path equivalence."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from q2lsp.core.types import CompletionItem
from q2lsp.lsp.completions import get_completions as get_lsp_completions
from q2lsp.lsp.types import (
    CompletionContext,
    CompletionMode,
    ParsedCommand,
    TokenSpan,
)
from q2lsp.usecases.get_completions_usecase import (
    CompletionRequest,
    get_completions as get_usecase_completions,
)


def _to_command(tokens: tuple[str, ...]) -> ParsedCommand:
    spans: list[TokenSpan] = []
    start = 0
    for token in tokens:
        end = start + len(token)
        spans.append(TokenSpan(text=token, start=start, end=end))
        start = end + 1
    end = spans[-1].end if spans else 0
    return ParsedCommand(tokens=spans, start=0, end=end)


def _to_rows(
    items: Sequence[CompletionItem],
) -> list[tuple[str, str, str]]:
    return [(item.label, item.detail, str(item.kind)) for item in items]


@pytest.mark.parametrize(
    ("mode", "prefix", "tokens"),
    [
        (CompletionMode.ROOT, "", ("qiime",)),
        (CompletionMode.PLUGIN, "", ("qiime", "feature-table")),
        (
            CompletionMode.PARAMETER,
            "--",
            ("qiime", "feature-table", "summarize", "--i-table"),
        ),
    ],
)
def test_lsp_wrapper_matches_usecase_completion_path(
    mode: CompletionMode,
    prefix: str,
    tokens: tuple[str, ...],
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
    request = CompletionRequest(mode=str(mode), prefix=prefix, command_tokens=tokens)
    context = CompletionContext(
        mode=mode,
        command=_to_command(tokens),
        current_token=None,
        token_index=len(tokens),
        prefix=prefix,
    )

    legacy_items = get_lsp_completions(context, hierarchy)
    usecase_items = get_usecase_completions(request, hierarchy)

    assert _to_rows(legacy_items) == _to_rows(usecase_items)
