"""Command-level diagnostics and dependency extraction."""

from __future__ import annotations

from q2lsp.lsp.diagnostics.models import (
    CommandAnalysis,
    CommandDependencies,
    DependencyReference,
)
from q2lsp.lsp.diagnostics.codes import UNKNOWN_OPTION
from q2lsp.lsp.diagnostics.stages import _has_help_invocation
from q2lsp.lsp.diagnostics.validator import validate_command_with_catalog
from q2lsp.lsp.types import ParsedCommand, TokenSpan
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.options import OptionGroup


def analyze_command(
    command: ParsedCommand, catalog: QiimeCatalog, source_text: str
) -> CommandAnalysis:
    """Collect command-level issues and dependency references."""
    issues = tuple(validate_command_with_catalog(command, catalog))

    if len(command.tokens) < 3:
        return CommandAnalysis(
            command=command,
            issues=issues,
            dependencies=CommandDependencies(),
        )

    command_name = command.tokens[1].text
    action_name = command.tokens[2].text
    if catalog.action(command_name, action_name) is None:
        return CommandAnalysis(
            command=command,
            issues=issues,
            dependencies=CommandDependencies(),
        )

    option_tokens = command.tokens[3:]
    option_groups = command.options
    flag_option_labels = {
        option.label
        for option in catalog.action_options(command_name, action_name)
        if option.is_bool_flag
    }
    if _has_help_invocation(
        option_tokens, option_groups, flag_option_labels
    ):
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
                    option_start=option.token.start,
                    option_end=option.token.end,
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
                option_start=option.token.start,
                option_end=option.token.end,
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
