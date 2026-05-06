"""Test helpers for completion logic."""

from __future__ import annotations

from q2lsp.adapters.completion_adapter import (
    get_used_parameters,
    to_completion_data,
)
from q2lsp.core.completion_engine import get_completions as get_core_completions
from q2lsp.core.types import (
    CompletionData,
    CompletionItem,
    CompletionMode,
    CompletionQuery,
)
from q2lsp.lsp.types import CompletionContext
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.types import JsonObject


def complete_root(root_node: JsonObject, prefix: str) -> list[CompletionItem]:
    """Get root-level completions (plugins + builtins)."""
    data = _to_completion_data(root_node)
    query = CompletionQuery(mode=CompletionMode.ROOT, prefix=prefix)
    return get_core_completions(query, data)


def complete_plugin(
    root_node: JsonObject,
    plugin_name: str,
    prefix: str,
) -> list[CompletionItem]:
    """Get plugin-level completions (actions)."""
    data = _to_completion_data(root_node)
    query = CompletionQuery(
        mode=CompletionMode.PLUGIN,
        prefix=prefix,
        plugin_name=plugin_name,
    )
    return get_core_completions(query, data)


def complete_parameters(
    root_node: JsonObject,
    plugin_name: str,
    action_name: str,
    prefix: str,
    used_params: set[str],
) -> list[CompletionItem]:
    """Get parameter-level completions for an action."""
    data = _to_completion_data(root_node)
    query = CompletionQuery(
        mode=CompletionMode.PARAMETER,
        prefix=prefix,
        normalized_prefix=prefix.lstrip("-"),
        plugin_name=plugin_name,
        action_name=action_name,
        used_parameters=frozenset(used_params),
    )
    return get_core_completions(query, data)


def ctx_get_used_parameters(ctx: CompletionContext) -> set[str]:
    """Extract used parameter names from a CompletionContext."""
    if ctx.command is None:
        return set()
    return get_used_parameters(tuple(token.text for token in ctx.command.tokens))


def _to_completion_data(root_node: JsonObject) -> CompletionData:
    return to_completion_data(QiimeCatalog.from_hierarchy({"qiime": root_node}))
