"""LSP-facing wrappers for completion logic."""

from __future__ import annotations

from q2lsp.adapters.completion_adapter import (
    get_used_parameters,
    option_matches_prefix,
    to_completion_data_from_root,
)
from q2lsp.core.completion_engine import get_completions as get_core_completions
from q2lsp.core.types import (
    COMPLETION_MODE_PARAMETER,
    COMPLETION_MODE_PLUGIN,
    COMPLETION_MODE_ROOT,
    CompletionItem,
    CompletionQuery,
)
from q2lsp.lsp.types import CompletionContext
from q2lsp.qiime.types import CommandHierarchy, JsonObject
from q2lsp.usecases.get_completions_usecase import (
    CompletionRequest,
    get_completions as get_usecase_completions,
)


def get_completions(
    ctx: CompletionContext,
    hierarchy: CommandHierarchy,
) -> list[CompletionItem]:
    """Get completion items based on LSP completion context."""
    command_tokens: tuple[str, ...] = ()
    if ctx.command is not None:
        command_tokens = tuple(token.text for token in ctx.command.tokens)
    request = CompletionRequest(
        mode=str(ctx.mode),
        prefix=ctx.prefix,
        command_tokens=command_tokens,
    )
    return get_usecase_completions(request, hierarchy)


def _get_used_parameters(ctx: CompletionContext) -> set[str]:
    if ctx.command is None:
        return set()
    return get_used_parameters(tuple(token.text for token in ctx.command.tokens))


def _option_matches_prefix(option_name: str, prefix_filter: str) -> bool:
    return option_matches_prefix(option_name, prefix_filter)


def _complete_root(root_node: JsonObject, prefix: str) -> list[CompletionItem]:
    data = to_completion_data_from_root(root_node)
    query = CompletionQuery(mode=COMPLETION_MODE_ROOT, prefix=prefix)
    return get_core_completions(query, data)


def _complete_plugin(
    root_node: JsonObject,
    plugin_name: str,
    prefix: str,
) -> list[CompletionItem]:
    data = to_completion_data_from_root(root_node)
    query = CompletionQuery(
        mode=COMPLETION_MODE_PLUGIN,
        prefix=prefix,
        plugin_name=plugin_name,
    )
    return get_core_completions(query, data)


def _complete_parameters(
    root_node: JsonObject,
    plugin_name: str,
    action_name: str,
    prefix: str,
    used_params: set[str],
) -> list[CompletionItem]:
    data = to_completion_data_from_root(root_node)
    query = CompletionQuery(
        mode=COMPLETION_MODE_PARAMETER,
        prefix=prefix,
        normalized_prefix=prefix.lstrip("-"),
        plugin_name=plugin_name,
        action_name=action_name,
        used_parameters=frozenset(used_params),
    )
    return get_core_completions(query, data)
