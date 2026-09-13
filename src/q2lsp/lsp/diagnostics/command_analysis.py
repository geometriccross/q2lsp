"""Command analysis: validation, dependency extraction, and matching.

Deep module that validates QIIME commands against the catalog,
extracts dependency references, and returns a unified CommandAnalysis.
"""

from __future__ import annotations

import difflib
from collections.abc import Mapping, Sequence
from typing import NamedTuple

from q2lsp.lsp.diagnostics import codes
from q2lsp.lsp.diagnostics.diagnostic_issue import DiagnosticIssue
from q2lsp.lsp.types import ParsedCommand, TokenSpan
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.catalog_facts import QiimeOptionFact
from q2lsp.qiime.option_tokens import (
    OptionGroup,
    group_option_tokens,
    normalize_option_to_param_name,
)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class DependencyReference(NamedTuple):
    """A dependency path reference anchored in the document."""

    path: str
    start: int
    end: int
    option_start: int
    option_end: int

    @property
    def anchor_start(self) -> int:
        if self.start < self.end:
            return self.start
        return self.option_start

    @property
    def anchor_end(self) -> int:
        if self.start < self.end:
            return self.end
        return self.option_end


class CommandDependencies(NamedTuple):
    """Dependency references extracted from a command."""

    inputs: tuple[DependencyReference, ...] = ()
    outputs: tuple[DependencyReference, ...] = ()


class CommandAnalysis(NamedTuple):
    """Command-level diagnostics and extracted dependency references."""

    command: ParsedCommand
    issues: tuple[DiagnosticIssue, ...]
    dependencies: CommandDependencies


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def analyze_command(
    command: ParsedCommand, catalog: QiimeCatalog, source_text: str
) -> CommandAnalysis:
    """Collect command-level issues and dependency references."""
    issues = tuple(_validate_command_with_catalog(command, catalog))

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
    if _has_help_invocation(option_tokens, option_groups, flag_option_labels):
        return CommandAnalysis(
            command=command,
            issues=issues,
            dependencies=CommandDependencies(),
        )

    invalid_option_spans = {
        (issue.start, issue.end)
        for issue in issues
        if issue.code == codes.UNKNOWN_OPTION
    }
    dependencies = _extract_command_dependencies(
        command,
        source_text,
        invalid_option_spans=invalid_option_spans,
    )
    return CommandAnalysis(command=command, issues=issues, dependencies=dependencies)


# ---------------------------------------------------------------------------
# Command validation orchestration
# ---------------------------------------------------------------------------


def _validate_command_with_catalog(
    command: ParsedCommand, catalog: QiimeCatalog
) -> list[DiagnosticIssue]:
    issues: list[DiagnosticIssue] = []

    token1_valid = True
    token1_for_action: str | None = None
    if len(command.tokens) >= 2:
        token1 = command.tokens[1]
        if not token1.text.startswith("-"):
            issue1 = _validate_plugin_or_builtin_with_catalog(token1, catalog)
            if issue1 is not None:
                issues.append(issue1)
                token1_valid = False
                token1_for_action = _get_unique_prefix_match(
                    token1.text, {command.name for command in catalog.commands()}
                )
            else:
                token1_for_action = token1.text

    token2_valid = True
    if (token1_valid or token1_for_action is not None) and len(command.tokens) >= 3:
        token2 = command.tokens[2]
        if not token2.text.startswith("-"):
            command_name = token1_for_action or command.tokens[1].text
            issue2 = _validate_action_with_catalog(token2, catalog, command_name)
            if issue2 is not None:
                issues.append(issue2)
                token2_valid = False

    if token1_valid and token2_valid and len(command.tokens) >= 3:
        token1 = command.tokens[1]
        token2 = command.tokens[2]
        plugin_name = token1.text
        action_name = token2.text
        option_issues: list[DiagnosticIssue] = []
        unknown_option_suggestions: dict[str, list[str]] = {}
        if len(command.tokens) >= 4:
            option_issues, unknown_option_suggestions = _validate_options_with_catalog(
                command.tokens[3:], catalog, plugin_name, action_name
            )
        issues.extend(option_issues)
        required_option_issues = _validate_required_options_with_catalog(
            command.tokens,
            catalog,
            plugin_name,
            action_name,
            unknown_option_suggestions,
        )
        issues.extend(required_option_issues)

    return issues


# ---------------------------------------------------------------------------
# Validation stages
# ---------------------------------------------------------------------------


def _validate_plugin_or_builtin_with_catalog(
    token: TokenSpan, catalog: QiimeCatalog
) -> DiagnosticIssue | None:
    token_text = token.text
    all_valid_names = [command.name for command in catalog.commands()]

    if _is_exact_match(token_text, all_valid_names):
        return None

    suggestions = _get_suggestions(token_text, all_valid_names, limit=3)
    if suggestions:
        message = f"Unknown QIIME command '{token_text}'. Did you mean {', '.join(repr(s) for s in suggestions)}?"
    else:
        message = f"Unknown QIIME command '{token_text}'."

    return DiagnosticIssue(
        message=message,
        start=token.start,
        end=token.end,
        code=codes.UNKNOWN_ROOT,
    )


def _validate_action_with_catalog(
    token: TokenSpan, catalog: QiimeCatalog, plugin_name: str
) -> DiagnosticIssue | None:
    token_text = token.text

    command = catalog.command(plugin_name)
    if command is None:
        return None

    if command.kind == "builtin" and not command.has_actions:
        return None

    valid_actions = [action.name for action in catalog.actions(plugin_name)]

    if _is_exact_match(token_text, valid_actions):
        return None

    code = (
        codes.UNKNOWN_SUBCOMMAND if command.kind == "builtin" else codes.UNKNOWN_ACTION
    )
    suggestions = _get_suggestions(token_text, valid_actions, limit=3)
    if suggestions:
        message = (
            f"Unknown action '{token_text}' for '{plugin_name}'. Did you mean "
            f"{', '.join(repr(s) for s in suggestions)}?"
        )
    else:
        message = f"Unknown action '{token_text}' for '{plugin_name}'."

    return DiagnosticIssue(
        message=message,
        start=token.start,
        end=token.end,
        code=code,
    )


def _validate_options_with_catalog(
    tokens: list[TokenSpan],
    catalog: QiimeCatalog,
    plugin_name: str,
    action_name: str,
) -> tuple[list[DiagnosticIssue], dict[str, list[str]]]:
    """Validate option tokens for a catalog-backed valid command path."""
    if catalog.action(plugin_name, action_name) is None:
        return [], {}

    option_facts = catalog.action_options(plugin_name, action_name)
    issues: list[DiagnosticIssue] = []
    unknown_option_suggestions: dict[str, list[str]] = {}
    valid_options = [option.label for option in option_facts]

    for option in group_option_tokens(tokens, lambda token: token.text):
        option_name = option.option_text
        if option_name in ("--help", "-h"):
            continue

        if not _is_exact_match(option_name, valid_options):
            suggestions = _get_suggestions(option_name, valid_options, limit=3)
            if suggestions:
                unknown_option_suggestions[option_name] = suggestions
                message = f"Unknown option '{option_name}'. Did you mean {', '.join(repr(s) for s in suggestions)}?"
            else:
                message = f"Unknown option '{option_name}'."

            issues.append(
                DiagnosticIssue(
                    message=message,
                    start=option.token.start,
                    end=option.token.end,
                    code=codes.UNKNOWN_OPTION,
                )
            )

    return issues, unknown_option_suggestions


def _validate_required_options_with_catalog(
    tokens: list[TokenSpan],
    catalog: QiimeCatalog,
    plugin_name: str,
    action_name: str,
    unknown_option_suggestions: Mapping[str, Sequence[str]],
) -> list[DiagnosticIssue]:
    """Validate required options for a catalog-backed valid command path."""
    option_facts = catalog.action_options(plugin_name, action_name)
    if not option_facts:
        return []

    return _validate_required_options_for_facts(
        tokens, option_facts, unknown_option_suggestions
    )


def _validate_required_options_for_facts(
    tokens: list[TokenSpan],
    option_facts: tuple[QiimeOptionFact, ...],
    unknown_option_suggestions: Mapping[str, Sequence[str]],
) -> list[DiagnosticIssue]:
    issues: list[DiagnosticIssue] = []

    if len(tokens) < 3:
        return issues

    option_tokens = tokens[3:]
    option_groups = group_option_tokens(option_tokens, lambda token: token.text)

    flag_option_labels = {
        option.label for option in option_facts if option.is_bool_flag
    }
    if _has_help_invocation(option_tokens, option_groups, flag_option_labels):
        return issues

    present_param_names: set[str] = set()
    for option in option_groups:
        param_name = normalize_option_to_param_name(option.option_text)
        if param_name is None:
            continue
        present_param_names.add(param_name.lower())

    required_param_options = {
        option.name.lower(): option.label for option in option_facts if option.required
    }
    missing_param_options = {
        param_name: option_label
        for param_name, option_label in required_param_options.items()
        if param_name not in present_param_names
    }

    suppressed_missing: set[str] = set()
    for suggestions in unknown_option_suggestions.values():
        if len(suggestions) != 1:
            continue
        suggestion_param_name = normalize_option_to_param_name(suggestions[0])
        if suggestion_param_name is None:
            continue
        suggestion_param_name_lower = suggestion_param_name.lower()
        if suggestion_param_name_lower in missing_param_options:
            suppressed_missing.add(suggestion_param_name_lower)

    action_token = tokens[2]
    for missing_param_name, missing_option in missing_param_options.items():
        if missing_param_name in suppressed_missing:
            continue
        issues.append(
            DiagnosticIssue(
                message=f"Required option '{missing_option}' is not specified.",
                start=action_token.start,
                end=action_token.end,
                code=codes.MISSING_REQUIRED_OPTION,
            )
        )

    return issues


# ---------------------------------------------------------------------------
# Help invocation detection
# ---------------------------------------------------------------------------


def _has_help_invocation(
    option_tokens: list[TokenSpan],
    option_groups: tuple[OptionGroup[TokenSpan], ...],
    flag_option_labels: set[str],
) -> bool:
    for option in option_groups:
        if option.option_text == "--help":
            return True

        for index, value_token in enumerate(option.value_tokens):
            if value_token.text != "-h":
                continue
            if option.option_text in flag_option_labels:
                return True
            if index == 0 and option.inline_value is None:
                continue
            return True

    if not option_groups:
        return any(token.text == "-h" for token in option_tokens)

    for token in option_tokens:
        token_text = token.text
        if token_text.startswith("--"):
            break
        if token_text == "-h":
            return True

    return False


# ---------------------------------------------------------------------------
# Matching and suggestions
# ---------------------------------------------------------------------------


def _is_exact_match(token_text: str, candidates: list[str] | set[str]) -> bool:
    """Check if token_text is an exact (case-insensitive) match of any candidate."""
    token_lower = token_text.lower()
    for candidate in candidates:
        candidate_lower = candidate.lower()
        if token_lower == candidate_lower:
            return True
    return False


def _get_suggestions(
    token_text: str, candidates: list[str] | set[str], *, limit: int = 3
) -> list[str]:
    """Get suggestions for token_text from candidates.

    Combines case-insensitive prefix matches and difflib close matches.
    Prefix matches are preferred (listed first).
    """
    if not candidates:
        return []

    token_lower = token_text.lower()
    suggestions: list[str] = []

    # First, collect case-insensitive prefix matches
    prefix_matches: list[str] = []
    for candidate in candidates:
        candidate_lower = candidate.lower()
        if candidate_lower.startswith(token_lower) and candidate_lower != token_lower:
            prefix_matches.append(candidate)

    # Deduplicate while preserving order
    seen: set[str] = set()
    for match in prefix_matches:
        if match not in seen:
            suggestions.append(match)
            seen.add(match)

    # Then, get difflib close matches
    close_matches = _get_close_matches(token_text, candidates, limit=limit)

    # Add close matches that aren't already in suggestions
    for match in close_matches:
        if match.lower() == token_lower:
            continue
        if match not in seen:
            suggestions.append(match)
            seen.add(match)

    # Limit to the requested number of suggestions
    return suggestions[:limit]


def _get_unique_prefix_match(
    token_text: str, candidates: list[str] | set[str]
) -> str | None:
    """Return a unique case-insensitive prefix match, if one exists."""
    token_lower = token_text.lower()
    matches = [
        candidate
        for candidate in candidates
        if candidate.lower().startswith(token_lower)
        and candidate.lower() != token_lower
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _get_close_matches(
    token_text: str, candidates: list[str] | set[str], *, limit: int = 3
) -> list[str]:
    """Get close matches for token_text from candidates using difflib."""
    if not candidates:
        return []

    cutoff = 0.6
    matches = difflib.get_close_matches(token_text, candidates, n=limit, cutoff=cutoff)
    return matches


# ---------------------------------------------------------------------------
# Dependency extraction
# ---------------------------------------------------------------------------


def _extract_command_dependencies(
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
