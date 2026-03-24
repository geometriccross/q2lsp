"""Command-level diagnostics and dependency extraction."""

from __future__ import annotations

from q2lsp.lsp.diagnostics.models import (
    CommandAnalysis,
    CommandDependencies,
    DependencyReference,
)
from q2lsp.lsp.diagnostics.codes import UNKNOWN_OPTION
from q2lsp.lsp.diagnostics.hierarchy import _get_root_node
from q2lsp.lsp.diagnostics.stages import _has_help_invocation
from q2lsp.lsp.diagnostics.validator import validate_command
from q2lsp.lsp.types import ParsedCommand, TokenSpan
from q2lsp.qiime.options import OptionGroup
from q2lsp.qiime.types import CommandHierarchy, JsonObject


def analyze_command(
    command: ParsedCommand, hierarchy: CommandHierarchy, source_text: str
) -> CommandAnalysis:
    """Collect command-level issues and dependency references."""
    issues = tuple(validate_command(command, hierarchy))

    action_node = _get_action_node(command, hierarchy)
    if action_node is None:
        return CommandAnalysis(
            command=command,
            issues=issues,
            dependencies=CommandDependencies(),
        )

    option_tokens = command.tokens[3:]
    option_groups = command.options
    if _has_help_invocation(option_tokens, option_groups, action_node):
        return CommandAnalysis(
            command=command,
            issues=issues,
            dependencies=CommandDependencies(),
        )

    invalid_option_spans = {
        (issue.start, issue.end) for issue in issues if issue.code == UNKNOWN_OPTION
    }
    dependencies = extract_command_dependencies(
        command,
        source_text,
        invalid_option_spans=invalid_option_spans,
    )
    return CommandAnalysis(command=command, issues=issues, dependencies=dependencies)


def extract_command_dependencies(
    command: ParsedCommand,
    source_text: str,
    *,
    invalid_option_spans: set[tuple[int, int]] | None = None,
) -> CommandDependencies:
    """Extract input and output dependency paths from grouped command options."""
    inputs: list[DependencyReference] = []
    outputs: list[DependencyReference] = []
    invalid_option_spans = invalid_option_spans or set()

    for option in command.options:
        if (option.token.start, option.token.end) in invalid_option_spans:
            continue
        if _is_dependency_input_option(option.option_text):
            inputs.extend(_iter_option_value_references(option, source_text))
            continue
        if _is_dependency_output_option(option.option_text):
            outputs.extend(_iter_option_value_references(option, source_text))

    return CommandDependencies(inputs=tuple(inputs), outputs=tuple(outputs))


def _get_action_node(
    command: ParsedCommand, hierarchy: CommandHierarchy
) -> JsonObject | None:
    if len(command.tokens) < 3:
        return None

    plugin_token = command.tokens[1]
    action_token = command.tokens[2]
    if plugin_token.text.startswith("-") or action_token.text.startswith("-"):
        return None

    root_node = _get_root_node(hierarchy)
    if not isinstance(root_node, dict):
        return None

    plugin_node = _get_case_insensitive_child(root_node, plugin_token.text)
    if not isinstance(plugin_node, dict):
        return None

    action_node = _get_case_insensitive_child(plugin_node, action_token.text)
    if not isinstance(action_node, dict):
        return None

    return action_node


def _get_case_insensitive_child(node: JsonObject, key: str) -> object | None:
    exact = node.get(key)
    if exact is not None:
        return exact

    key_lower = key.lower()
    for candidate, value in node.items():
        if candidate.lower() == key_lower:
            return value

    return None


def _is_dependency_input_option(option_text: str) -> bool:
    return option_text == "--input-path" or option_text.startswith("--i-")


def _is_dependency_output_option(option_text: str) -> bool:
    return option_text == "--output-path" or option_text.startswith("--o-")


def _iter_option_value_references(
    option: OptionGroup[TokenSpan], source_text: str
) -> tuple[DependencyReference, ...]:
    references: list[DependencyReference] = []

    if option.inline_value:
        inline_span = _get_inline_value_span(option.token, source_text)
        if inline_span is not None:
            references.append(
                DependencyReference(
                    path=option.inline_value,
                    start=inline_span[0],
                    end=inline_span[1],
                )
            )

    for value_token in option.value_tokens:
        if not value_token.text:
            continue
        references.append(
            DependencyReference(
                path=value_token.text,
                start=value_token.start,
                end=value_token.end,
            )
        )

    return tuple(references)


def _get_inline_value_span(
    token: TokenSpan, source_text: str
) -> tuple[int, int] | None:
    raw_token = source_text[token.start : token.end]
    equals_offset = raw_token.find("=")
    if equals_offset < 0:
        return None

    value_fragment = raw_token[equals_offset + 1 :]
    start = token.start + equals_offset + 1
    end = token.end
    if len(value_fragment) >= 2 and value_fragment[0] in {'"', "'"}:
        if value_fragment[-1] == value_fragment[0]:
            start += 1
            end -= 1

    if start > end:
        return None
    return start, end
