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
from q2lsp.qiime.hierarchy_keys import COMMAND_METADATA_KEYS
from q2lsp.qiime.options import (
    format_qiime_option_label,
    group_option_tokens,
    OptionGroup,
    normalize_option_to_param_name,
    option_label_matches_prefix,
    param_is_required,
)
from q2lsp.qiime.signature_params import iter_signature_params
from q2lsp.qiime.types import JsonObject


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
    """Normalize catalog command data into core completion data."""
    root_items: list[CompletionItem] = []
    commands: list[CommandCandidate] = []

    for command_name in catalog.command_names:
        command_node = catalog.command_node(command_name)
        if command_node is None:
            continue

        is_builtin = catalog.is_builtin(command_name)
        root_items.append(
            CompletionItem(
                label=command_name,
                detail=_command_detail(command_node, is_builtin=is_builtin),
                kind=CompletionKind.BUILTIN if is_builtin else CompletionKind.PLUGIN,
            )
        )
        commands.append(
            _to_command_candidate(
                name=command_name,
                command_node=command_node,
                is_builtin=is_builtin,
            )
        )

    return CompletionData(root_items=tuple(root_items), commands=tuple(commands))


def get_used_parameters(command_tokens: tuple[str, ...] | ParsedCommand) -> set[str]:
    """Extract normalized parameter names from command tokens."""
    used: set[str] = set()
    option_groups = _group_command_options(command_tokens)
    for option in option_groups:
        param_name = normalize_option_to_param_name(option.option_text)
        if param_name:
            used.add(param_name)
    return used


def option_matches_prefix(option_name: str, prefix_filter: str) -> bool:
    """Match completion option names with user prefix text."""
    return option_label_matches_prefix(option_name, prefix_filter)


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


def _command_detail(command_node: JsonObject, *, is_builtin: bool) -> str:
    if is_builtin:
        return str(command_node.get("short_help", "")) or str(
            command_node.get("help", "")
        ) or "Built-in command"
    return str(command_node.get("short_description", "")) or str(
        command_node.get("description", "")
    ) or "Plugin"


def _to_command_candidate(
    *,
    name: str,
    command_node: JsonObject,
    is_builtin: bool,
) -> CommandCandidate:
    actions: list[ActionCandidate] = []
    for key, value in command_node.items():
        if key in COMMAND_METADATA_KEYS:
            continue
        if not isinstance(value, dict):
            continue
        value_json = cast(JsonObject, value)

        detail = str(value_json.get("description", ""))
        actions.append(
            ActionCandidate(
                item=CompletionItem(
                    label=key,
                    detail=detail or "Action",
                    kind=CompletionKind.ACTION,
                ),
                parameters=_to_parameter_candidates(value_json),
            )
        )

    return CommandCandidate(
        name=name,
        is_builtin=is_builtin,
        actions=tuple(actions),
    )


def _to_parameter_candidates(action_node: JsonObject) -> tuple[ParameterCandidate, ...]:
    parameters: list[ParameterCandidate] = []
    for name, option_prefix, param in iter_signature_params(action_node):
        option_name = format_qiime_option_label(option_prefix, name)

        detail_parts: list[str] = []
        param_type = param.get("type", "")
        if param_type:
            detail_parts.append(f"[{param_type}]")
        description = param.get("description", "")
        if description:
            detail_parts.append(str(description))

        if param_is_required(param):
            detail_parts.insert(0, "(required)")

        parameters.append(
            ParameterCandidate(
                name=name,
                item=CompletionItem(
                    label=option_name,
                    detail=" ".join(detail_parts) if detail_parts else "Parameter",
                    kind=CompletionKind.PARAMETER,
                ),
                match_texts=_to_parameter_match_texts(option_name),
            )
        )
    return tuple(parameters)


def _to_parameter_match_texts(option_name: str) -> tuple[str, ...]:
    bare = option_name.lstrip("-")
    if len(bare) >= 2 and bare[0] in {"i", "o", "p", "m"} and bare[1] == "-":
        bare = bare[2:]
    return (bare,)
