"""Adapters for completion flow boundaries."""

from __future__ import annotations

from typing import Any, cast

from q2lsp.core.types import (
    ActionCandidate,
    CommandCandidate,
    CompletionData,
    CompletionKind,
    CompletionItem,
    CompletionMode,
    CompletionQuery,
    ParameterCandidate,
)
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.catalog_facts import QiimeOptionFact
from q2lsp.qiime.option_tokens import (
    group_option_tokens,
    OptionGroup,
    normalize_option_to_param_name,
)


def to_completion_query(
    *,
    mode: str,
    prefix: str,
    command_tokens: tuple[str, ...],
) -> CompletionQuery:
    """Map boundary input values to a pure completion query."""
    resolved_mode = _to_completion_mode(mode)
    if not command_tokens:
        resolved_mode = CompletionMode.NONE

    return CompletionQuery(
        mode=resolved_mode,
        prefix=prefix,
        normalized_prefix=prefix.lstrip("-"),
        plugin_name=_get_token_text(command_tokens, 1),
        action_name=_get_token_text(command_tokens, 2),
        used_parameters=frozenset(get_used_parameters(command_tokens)),
    )


def to_completion_data(catalog: QiimeCatalog) -> CompletionData:
    """Normalize catalog command facts into core completion data."""
    root_items: list[CompletionItem] = []
    commands: list[CommandCandidate] = []

    for command in catalog.commands():
        is_builtin = command.kind == "builtin"
        root_items.append(
            CompletionItem(
                label=command.name,
                detail=_command_detail(command.summary, is_builtin=is_builtin),
                kind=CompletionKind.BUILTIN if is_builtin else CompletionKind.PLUGIN,
            )
        )
        commands.append(
            CommandCandidate(
                name=command.name,
                is_builtin=is_builtin,
                actions=tuple(
                    ActionCandidate(
                        item=CompletionItem(
                            label=action.name,
                            detail=action.summary or "Action",
                            kind=CompletionKind.ACTION,
                        ),
                        parameters=_to_parameter_candidates(
                            catalog.action_options(command.name, action.name)
                        ),
                    )
                    for action in catalog.actions(command.name)
                ),
            )
        )

    return CompletionData(root_items=tuple(root_items), commands=tuple(commands))


def get_used_parameters(command_tokens: Any) -> set[str]:
    """Extract normalized parameter names from command tokens."""
    used: set[str] = set()
    option_groups = _group_command_options(command_tokens)
    for option in option_groups:
        param_name = normalize_option_to_param_name(option.option_text)
        if param_name:
            used.add(param_name)
    return used


def _group_command_options(
    command_tokens: Any,
) -> tuple[OptionGroup[Any], ...]:
    options = getattr(command_tokens, "options", None)
    if options is not None:
        return cast(tuple[OptionGroup[Any], ...], options)
    return group_option_tokens(
        cast(tuple[str, ...], command_tokens),
        lambda token: token,
        start_index=3,
    )


def _to_completion_mode(mode: str) -> CompletionMode:
    if mode == CompletionMode.ROOT:
        return CompletionMode.ROOT
    if mode == CompletionMode.PLUGIN:
        return CompletionMode.PLUGIN
    if mode == CompletionMode.PARAMETER:
        return CompletionMode.PARAMETER
    return CompletionMode.NONE


def _get_token_text(command_tokens: tuple[str, ...], index: int) -> str:
    if index >= len(command_tokens):
        return ""
    return command_tokens[index]


def _command_detail(summary: str, *, is_builtin: bool) -> str:
    if summary:
        return summary
    if is_builtin:
        return "Built-in command"
    return "Plugin"


def _to_parameter_candidates(
    option_facts: tuple[QiimeOptionFact, ...],
) -> tuple[ParameterCandidate, ...]:
    parameters: list[ParameterCandidate] = []
    for option in option_facts:
        detail_parts: list[str] = []
        if option.value_type:
            detail_parts.append(f"[{option.value_type}]")
        if option.description:
            detail_parts.append(option.description)

        if option.required:
            detail_parts.insert(0, "(required)")

        parameters.append(
            ParameterCandidate(
                name=option.name,
                item=CompletionItem(
                    label=option.label,
                    detail=" ".join(detail_parts) if detail_parts else "Parameter",
                    kind=CompletionKind.PARAMETER,
                ),
                match_texts=_to_parameter_match_texts(option.label),
            )
        )
    return tuple(parameters)


def _to_parameter_match_texts(option_name: str) -> tuple[str, ...]:
    bare = option_name.lstrip("-")
    if len(bare) >= 2 and bare[0] in {"i", "o", "p", "m"} and bare[1] == "-":
        bare = bare[2:]
    return (bare,)
