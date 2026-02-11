"""Validator module for QIIME2 command diagnostics.

Provides pure validation logic that takes parsed commands + hierarchy
and returns issues with spans and suggestions.
"""

from __future__ import annotations

from typing import NamedTuple

from q2lsp.lsp.diagnostics.hierarchy import (
    _get_root_node,
    _get_valid_plugins_and_builtins,
)
from q2lsp.lsp.diagnostics.matching import _get_unique_prefix_match
from q2lsp.lsp.types import ParsedCommand
from q2lsp.qiime.types import CommandHierarchy


class DiagnosticIssue(NamedTuple):
    """A diagnostic issue for a command."""

    message: str  # The diagnostic message
    start: int  # Start offset in the document
    end: int  # End offset in the document (exclusive)
    code: str  # Diagnostic code (e.g., "q2lsp-dni/unknown-root")


def validate_command(
    command: ParsedCommand, hierarchy: CommandHierarchy
) -> list[DiagnosticIssue]:
    """
    Validate a QIIME command and return diagnostic issues.

    Args:
        command: The parsed QIIME command.
        hierarchy: The QIIME2 command hierarchy.

    Returns:
        List of DiagnosticIssue for any problems found.
    """
    from q2lsp.lsp.diagnostics.stages import (
        _validate_action,
        _validate_options,
        _validate_plugin_or_builtin,
        _validate_required_options,
    )

    issues: list[DiagnosticIssue] = []

    # Get the root node (usually "qiime")
    root_node = _get_root_node(hierarchy)
    if root_node is None:
        return issues

    # Validate token 1 (plugin/builtin) when len(tokens) >= 2
    token1_valid = True
    token1_for_action: str | None = None
    if len(command.tokens) >= 2:
        token1 = command.tokens[1]
        # Skip if token starts with '-' (option-like)
        if not token1.text.startswith("-"):
            issue1 = _validate_plugin_or_builtin(token1, root_node)
            if issue1 is not None:
                issues.append(issue1)
                token1_valid = False
                valid_plugins, valid_builtins = _get_valid_plugins_and_builtins(
                    root_node
                )
                token1_for_action = _get_unique_prefix_match(
                    token1.text, valid_plugins | valid_builtins
                )
            else:
                token1_for_action = token1.text

    # Validate token 2 (action) when len(tokens) >= 3 and token1 is valid
    # If token1 is invalid, we don't validate token2 to avoid noise
    # (action candidates are unknown when the plugin/builtin is invalid)
    token2_valid = True
    if (token1_valid or token1_for_action is not None) and len(command.tokens) >= 3:
        token2 = command.tokens[2]
        # Skip if token starts with '-' (option-like)
        if not token2.text.startswith("-"):
            plugin_name = token1_for_action or command.tokens[1].text
            issue2 = _validate_action(token2, root_node, plugin_name)
            if issue2 is not None:
                issues.append(issue2)
                token2_valid = False

    # Validate options and required options when token1/token2 are valid.
    if token1_valid and token2_valid and len(command.tokens) >= 3:
        token1 = command.tokens[1]
        token2 = command.tokens[2]
        plugin_name = token1.text
        action_name = token2.text
        option_issues: list[DiagnosticIssue] = []
        if len(command.tokens) >= 4:
            option_issues = _validate_options(
                command.tokens[3:], root_node, plugin_name, action_name
            )
        issues.extend(option_issues)
        required_option_issues = _validate_required_options(
            command.tokens,
            root_node,
            plugin_name,
            action_name,
            option_issues,
        )
        issues.extend(required_option_issues)

    return issues
