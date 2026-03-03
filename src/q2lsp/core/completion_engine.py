"""Pure completion decision engine for QIIME2 commands."""

from __future__ import annotations

from q2lsp.core.types import (
    ActionCandidate,
    CommandCandidate,
    CompletionData,
    CompletionItem,
    CompletionKind,
    CompletionMode,
    CompletionQuery,
)


def get_completions(
    query: CompletionQuery,
    data: CompletionData,
) -> list[CompletionItem]:
    """Get completion items for a pure completion query."""
    if query.mode == CompletionMode.NONE:
        return []

    if query.mode == CompletionMode.ROOT:
        return complete_root(data, query.prefix)
    if query.mode == CompletionMode.PLUGIN:
        return complete_plugin(data, query.plugin_name, query.prefix)
    if query.mode == CompletionMode.PARAMETER:
        return complete_parameters(
            data,
            query.plugin_name,
            query.action_name,
            query.prefix,
            query.normalized_prefix,
            set(query.used_parameters),
        )

    return []


def complete_root(data: CompletionData, prefix: str) -> list[CompletionItem]:
    return [item for item in data.root_items if item.label.startswith(prefix)]


def complete_plugin(
    data: CompletionData,
    plugin_name: str,
    prefix: str,
) -> list[CompletionItem]:
    command = _find_command(data.commands, plugin_name)
    if command is None:
        return []

    items = [
        action.item
        for action in command.actions
        if action.item.label.startswith(prefix)
    ]
    if not items and command.is_builtin:
        return _complete_builtin_options(prefix)

    return items


def _complete_builtin_options(prefix: str) -> list[CompletionItem]:
    options = [("--help", "Show help message")]
    items: list[CompletionItem] = []
    for opt, desc in options:
        if opt.startswith(prefix):
            items.append(
                CompletionItem(
                    label=opt,
                    detail=desc,
                    kind=CompletionKind.PARAMETER,
                )
            )
    return items


def complete_parameters(
    data: CompletionData,
    plugin_name: str,
    action_name: str,
    prefix: str,
    normalized_prefix: str,
    used_params: set[str],
) -> list[CompletionItem]:
    command = _find_command(data.commands, plugin_name)
    if command is None:
        return []

    action = _find_action(command.actions, action_name)
    if action is None:
        return []

    if not action.parameters:
        if command.is_builtin:
            return _complete_builtin_options(prefix)
        return []

    items: list[CompletionItem] = []
    for parameter in action.parameters:
        if parameter.name in used_params:
            continue
        if not _parameter_matches_prefix(
            parameter.match_texts,
            parameter.item.label,
            prefix,
            normalized_prefix,
        ):
            continue
        items.append(parameter.item)

    if "--help".startswith(prefix) and "help" not in used_params:
        items.append(
            CompletionItem(
                label="--help",
                detail="Show help message",
                kind=CompletionKind.PARAMETER,
            )
        )

    return items


def _find_command(
    commands: tuple[CommandCandidate, ...],
    name: str,
) -> CommandCandidate | None:
    for command in commands:
        if command.name == name:
            return command
    return None


def _find_action(
    actions: tuple[ActionCandidate, ...],
    name: str,
) -> ActionCandidate | None:
    for action in actions:
        if action.item.label == name:
            return action
    return None


def _parameter_matches_prefix(
    match_texts: tuple[str, ...],
    option_label: str,
    prefix: str,
    normalized_prefix: str,
) -> bool:
    if not prefix:
        return True
    if option_label.startswith(prefix):
        return True

    normalized = normalized_prefix or prefix.lstrip("-")
    if not normalized:
        return False
    return any(text.startswith(normalized) for text in match_texts)
