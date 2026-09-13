"""Completion candidates from the command context and QIIME catalog."""

from __future__ import annotations

from q2lsp.core.types import CompletionItem, CompletionKind, CompletionMode
from q2lsp.lsp.types import CompletionContext
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.catalog_facts import QiimeOptionFact
from q2lsp.qiime.option_tokens import normalize_option_to_param_name


def get_completions(
    context: CompletionContext, catalog: QiimeCatalog
) -> list[CompletionItem]:
    if context.command is None or context.mode == CompletionMode.NONE:
        return []

    prefix = context.prefix
    if context.mode == CompletionMode.ROOT:
        return [
            CompletionItem(
                label=command.name,
                detail=command.summary
                or ("Built-in command" if command.kind == "builtin" else "Plugin"),
                kind=CompletionKind.BUILTIN
                if command.kind == "builtin"
                else CompletionKind.PLUGIN,
            )
            for command in catalog.commands()
            if command.name.startswith(prefix)
        ]

    tokens = context.command.tokens
    command = catalog.command(tokens[1].text)
    if command is None:
        return []

    if context.mode == CompletionMode.PLUGIN:
        items = [
            CompletionItem(
                label=action.name,
                detail=action.summary or "Action",
                kind=CompletionKind.ACTION,
            )
            for action in catalog.actions(command.name)
            if action.name.startswith(prefix)
        ]
        if not items and command.kind == "builtin":
            return _complete_help(prefix)
        return items

    action = catalog.action(command.name, tokens[2].text)
    if action is None:
        return []

    options = catalog.action_options(command.name, action.name)
    if not options:
        return _complete_help(prefix) if command.kind == "builtin" else []

    used_parameters = {
        name
        for option in context.command.options
        if (name := normalize_option_to_param_name(option.option_text)) is not None
    }
    items = [
        CompletionItem(
            label=option.label,
            detail=_option_detail(option),
            kind=CompletionKind.PARAMETER,
        )
        for option in options
        if option.name not in used_parameters
        and _parameter_matches_prefix(option.label, prefix)
    ]
    if "help" not in used_parameters:
        items.extend(_complete_help(prefix))
    return items


def _complete_help(prefix: str) -> list[CompletionItem]:
    if not "--help".startswith(prefix):
        return []
    return [
        CompletionItem(
            label="--help",
            detail="Show help message",
            kind=CompletionKind.PARAMETER,
        )
    ]


def _option_detail(option: QiimeOptionFact) -> str:
    parts: list[str] = []
    if option.required:
        parts.append("(required)")
    if option.value_type:
        parts.append(f"[{option.value_type}]")
    if option.description:
        parts.append(option.description)
    return " ".join(parts) or "Parameter"


def _parameter_matches_prefix(label: str, prefix: str) -> bool:
    if label.startswith(prefix):
        return True
    bare = label.lstrip("-")
    if len(bare) >= 2 and bare[0] in {"i", "o", "p", "m"} and bare[1] == "-":
        bare = bare[2:]
    normalized = prefix.lstrip("-")
    return bool(normalized) and bare.startswith(normalized)
