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
from q2lsp.lsp.types import ParsedCommand
from q2lsp.qiime.hierarchy_keys import COMMAND_METADATA_KEYS, ROOT_METADATA_KEYS
from q2lsp.qiime.options import (
    format_qiime_option_label,
    group_option_tokens,
    OptionGroup,
    normalize_option_to_param_name,
    option_label_matches_prefix,
    param_is_required,
)
from q2lsp.qiime.signature_params import iter_signature_params
from q2lsp.qiime.types import CommandHierarchy, JsonObject


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


def to_completion_data(hierarchy: CommandHierarchy) -> CompletionData:
    """Normalize external hierarchy data into core completion data."""
    root_node = _get_root_node(hierarchy)
    if root_node is None:
        return CompletionData()
    return to_completion_data_from_root(root_node)


def to_completion_data_from_root(root_node: JsonObject) -> CompletionData:
    """Normalize a root command node into core completion data."""
    builtins = _builtin_names(root_node)
    builtins_set = set(builtins)

    root_items: list[CompletionItem] = []
    commands: list[CommandCandidate] = []

    for builtin_name in builtins:
        builtin_node = root_node.get(builtin_name)
        detail = ""
        if isinstance(builtin_node, dict):
            builtin_json = cast(JsonObject, builtin_node)
            detail = str(builtin_json.get("short_help", "")) or str(
                builtin_json.get("help", "")
            )
            commands.append(
                _to_command_candidate(
                    name=builtin_name,
                    command_node=builtin_json,
                    is_builtin=True,
                )
            )
        root_items.append(
            CompletionItem(
                label=builtin_name,
                detail=detail or "Built-in command",
                kind=CompletionKind.BUILTIN,
            )
        )

    for key, value in root_node.items():
        if key in ROOT_METADATA_KEYS or key in builtins_set:
            continue
        if not isinstance(value, dict):
            continue
        value_json = cast(JsonObject, value)

        detail = str(value_json.get("short_description", "")) or str(
            value_json.get("description", "")
        )
        root_items.append(
            CompletionItem(
                label=key,
                detail=detail or "Plugin",
                kind=CompletionKind.PLUGIN,
            )
        )
        commands.append(
            _to_command_candidate(name=key, command_node=value_json, is_builtin=False)
        )

    return CompletionData(
        root_items=tuple(root_items),
        commands=tuple(commands),
    )


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


def _get_root_node(hierarchy: CommandHierarchy) -> JsonObject | None:
    if not hierarchy:
        return None
    root_node = next(iter(hierarchy.values()), None)
    if isinstance(root_node, dict):
        return root_node
    return None


def _get_token_text(command_tokens: tuple[str, ...], index: int) -> str:
    if index >= len(command_tokens):
        return ""
    return command_tokens[index]


def _group_command_options(
    command_tokens: tuple[str, ...] | ParsedCommand,
) -> tuple[OptionGroup[Any], ...]:
    if isinstance(command_tokens, ParsedCommand):
        return command_tokens.options
    return group_option_tokens(command_tokens, lambda token: token, start_index=3)


def _builtin_names(root_node: JsonObject) -> list[str]:
    builtins = root_node.get("builtins", [])
    if not isinstance(builtins, list):
        return []
    return [name for name in builtins if isinstance(name, str)]


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
