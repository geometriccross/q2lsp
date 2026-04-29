"""Validator module for QIIME2 command diagnostics.

Provides pure validation logic that takes parsed commands + catalog
and returns issues with spans and suggestions.
"""

from __future__ import annotations

from q2lsp.lsp.diagnostics.diagnostic_issue import DiagnosticIssue
from q2lsp.lsp.diagnostics.matching import _get_unique_prefix_match
from q2lsp.lsp.diagnostics.stages import (
    _validate_action_with_catalog,
    _validate_options_with_catalog,
    _validate_plugin_or_builtin_with_catalog,
    _validate_required_options_with_catalog,
)
from q2lsp.lsp.types import ParsedCommand
from q2lsp.qiime.catalog import QiimeCatalog


def validate_command_with_catalog(
    command: ParsedCommand, catalog: QiimeCatalog
) -> list[DiagnosticIssue]:
    issues: list[DiagnosticIssue] = []
    root_node = catalog.root_node()
    if root_node is None:
        return issues

    token1_valid = True
    token1_for_action: str | None = None
    if len(command.tokens) >= 2:
        token1 = command.tokens[1]
        if not token1.text.startswith("-"):
            issue1 = _validate_plugin_or_builtin_with_catalog(token1, catalog)
            if issue1 is not None:
                issues.append(issue1)
                token1_valid = False
                valid_plugins, valid_builtins = catalog.valid_plugins_and_builtins()
                token1_for_action = _get_unique_prefix_match(
                    token1.text, valid_plugins | valid_builtins
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
