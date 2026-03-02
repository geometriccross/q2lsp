"""Use case for querying completion suggestions."""

from __future__ import annotations

from typing import NamedTuple

from q2lsp.adapters.completion_adapter import to_completion_data, to_completion_query
from q2lsp.core.completion_engine import get_completions as get_core_completions
from q2lsp.core.types import CompletionItem
from q2lsp.qiime.types import CommandHierarchy


class CompletionRequest(NamedTuple):
    """Boundary input for completion usecase."""

    mode: str
    prefix: str
    command_tokens: tuple[str, ...]


def get_completions(
    request: CompletionRequest,
    hierarchy: CommandHierarchy,
) -> list[CompletionItem]:
    """Return completion suggestions from boundary request and command hierarchy."""
    query = to_completion_query(
        mode=request.mode,
        prefix=request.prefix,
        command_tokens=request.command_tokens,
    )
    data = to_completion_data(hierarchy)
    return get_core_completions(query, data)
