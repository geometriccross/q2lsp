"""Validator module for QIIME2 command diagnostics.

Provides pure validation logic that takes parsed commands + hierarchy
and returns issues with spans and suggestions.
"""

from __future__ import annotations

import difflib
from typing import NamedTuple

from q2lsp.lsp.types import ParsedCommand, TokenSpan
from q2lsp.qiime.options import format_qiime_option_label, qiime_option_prefix
from q2lsp.qiime.types import CommandHierarchy, JsonObject


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
    issues: list[DiagnosticIssue] = []

    # Get the root node (usually "qiime")
    root_node = _get_root_node(hierarchy)
    if root_node is None:
        return issues

    # Validate token 1 (plugin/builtin) when len(tokens) >= 2
    token1_valid = True
    if len(command.tokens) >= 2:
        token1 = command.tokens[1]
        # Skip if token starts with '-' (option-like)
        if not token1.text.startswith("-"):
            issue1 = _validate_plugin_or_builtin(token1, root_node)
            if issue1 is not None:
                issues.append(issue1)
                token1_valid = False

    # Validate token 2 (action) when len(tokens) >= 3 and token1 is valid
    # If token1 is invalid, we don't validate token2 to avoid noise
    # (action candidates are unknown when the plugin/builtin is invalid)
    token2_valid = True
    if token1_valid and len(command.tokens) >= 3:
        token2 = command.tokens[2]
        # Skip if token starts with '-' (option-like)
        if not token2.text.startswith("-"):
            token1 = command.tokens[1]
            plugin_name = token1.text
            issue2 = _validate_action(token2, root_node, plugin_name)
            if issue2 is not None:
                issues.append(issue2)
                token2_valid = False

    # Validate options when len(tokens) >= 4 and both token1 and token2 are valid
    if token1_valid and token2_valid and len(command.tokens) >= 4:
        token1 = command.tokens[1]
        token2 = command.tokens[2]
        plugin_name = token1.text
        action_name = token2.text
        option_issues = _validate_options(
            command.tokens[3:], root_node, plugin_name, action_name
        )
        issues.extend(option_issues)

    return issues


def _get_root_node(hierarchy: CommandHierarchy) -> JsonObject | None:
    """Get the root node from hierarchy (usually 'qiime')."""
    if not hierarchy:
        return None
    return next(iter(hierarchy.values()), None)


def _is_builtin_leaf(node: JsonObject) -> bool:
    """
    Check if a node is a builtin leaf (has no subcommands).

    Args:
        node: The plugin/builtin node to check.

    Returns:
        True if the node has no subcommands (leaf), False otherwise.
    """
    # If it's a builtin (type == "builtin"), check if it has subcommands
    if node.get("type") == "builtin":
        # A builtin is a leaf if it has no action/subcommand keys
        # Actions are keys that are not metadata
        metadata_keys = {
            "id",
            "name",
            "version",
            "website",
            "user_support_text",
            "description",
            "short_description",
            "short_help",
            "help",
            "actions",
            "type",
            "builtins",
        }
        for key, value in node.items():
            if key not in metadata_keys and isinstance(value, dict):
                return False
        return True
    return False


def _validate_plugin_or_builtin(
    token: TokenSpan, root_node: JsonObject
) -> DiagnosticIssue | None:
    """
    Validate a plugin or builtin token (token 1).

    Returns None if token is valid, otherwise a DiagnosticIssue.
    """
    token_text = token.text

    # Get all valid plugin names and builtin names
    valid_plugins, valid_builtins = _get_valid_plugins_and_builtins(root_node)
    all_valid_names = list(valid_plugins | valid_builtins)

    # If token matches exactly (case-insensitive), no issue
    if _is_exact_match(token_text, all_valid_names):
        return None

    # Get suggestions (prefix matches + difflib)
    suggestions = _get_suggestions(token_text, all_valid_names, limit=3)
    if suggestions:
        message = f"Unknown QIIME command '{token_text}'. Did you mean {', '.join(repr(s) for s in suggestions)}?"
    else:
        message = f"Unknown QIIME command '{token_text}'."

    return DiagnosticIssue(
        message=message,
        start=token.start,
        end=token.end,
        code="q2lsp-dni/unknown-root",
    )


def _validate_action(
    token: TokenSpan, root_node: JsonObject, plugin_name: str
) -> DiagnosticIssue | None:
    """
    Validate an action token (token 2).

    Returns None if token is valid, otherwise a DiagnosticIssue.
    """
    token_text = token.text

    # Get the plugin node
    plugin_node = root_node.get(plugin_name)
    if not isinstance(plugin_node, dict):
        # Plugin doesn't exist - will be caught by token1 validation
        return None

    # Builtins with no subcommands: do not validate token2
    if _is_builtin_leaf(plugin_node):
        return None

    # Get all valid action names for this plugin
    valid_actions = _get_valid_actions(plugin_node)

    # If token matches exactly (case-insensitive), no issue
    if _is_exact_match(token_text, valid_actions):
        return None

    # Determine code based on whether parent is a builtin or plugin
    is_builtin = plugin_node.get("type") == "builtin"
    code = "q2lsp-dni/unknown-subcommand" if is_builtin else "q2lsp-dni/unknown-action"

    # Get suggestions (prefix matches + difflib)
    suggestions = _get_suggestions(token_text, valid_actions, limit=3)
    if suggestions:
        message = f"Unknown action '{token_text}' for '{plugin_name}'. Did you mean {', '.join(repr(s) for s in suggestions)}?"
    else:
        message = f"Unknown action '{token_text}' for '{plugin_name}'."

    return DiagnosticIssue(
        message=message,
        start=token.start,
        end=token.end,
        code=code,
    )


def _get_valid_plugins_and_builtins(root_node: JsonObject) -> tuple[set[str], set[str]]:
    """Extract valid plugin and builtin names from root node."""
    # Metadata keys to skip
    metadata_keys = {
        "name",
        "help",
        "short_help",
        "builtins",
    }

    # Get builtins
    builtins_data = root_node.get("builtins", [])
    valid_builtins = set()
    if isinstance(builtins_data, list):
        for name in builtins_data:
            if isinstance(name, str):
                valid_builtins.add(name)

    # Get plugins (keys that are not metadata)
    valid_plugins = set()
    for key, value in root_node.items():
        if not key:
            continue
        if key in metadata_keys:
            continue
        if key in valid_builtins:
            continue
        if not isinstance(value, dict):
            continue
        valid_plugins.add(key)

    return valid_plugins, valid_builtins


def _get_valid_actions(plugin_node: JsonObject) -> list[str]:
    """Extract valid action names from plugin node."""
    # Metadata keys to skip
    metadata_keys = {
        "id",
        "name",
        "version",
        "website",
        "user_support_text",
        "description",
        "short_description",
        "short_help",
        "help",
        "actions",
        "type",
    }

    valid_actions = []
    for key, value in plugin_node.items():
        if not key:
            continue
        if key in metadata_keys:
            continue
        if not isinstance(value, dict):
            continue
        valid_actions.append(key)

    return valid_actions


def _is_exact_match(token_text: str, candidates: list[str] | set[str]) -> bool:
    """
    Check if token_text is an exact (case-insensitive) match of any candidate.

    Args:
        token_text: The text to check.
        candidates: List or set of candidate strings.

    Returns:
        True if token_text matches exactly (case-insensitive).
    """
    token_lower = token_text.lower()
    for candidate in candidates:
        candidate_lower = candidate.lower()
        if token_lower == candidate_lower:
            return True
    return False


def _get_suggestions(
    token_text: str, candidates: list[str] | set[str], *, limit: int = 3
) -> list[str]:
    """
    Get suggestions for token_text from candidates.

    Combines case-insensitive prefix matches and difflib close matches.
    Prefix matches are preferred (listed first).

    Args:
        token_text: The text to find suggestions for.
        candidates: List or set of candidate strings.
        limit: Maximum number of suggestions to return.

    Returns:
        List of suggestions, ordered with prefix matches first, then close matches.
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
    seen = set()
    for match in prefix_matches:
        if match not in seen:
            suggestions.append(match)
            seen.add(match)

    # Then, get difflib close matches
    close_matches = _get_close_matches(token_text, candidates, limit=limit)

    # Add close matches that aren't already in suggestions
    for match in close_matches:
        if match not in seen:
            suggestions.append(match)
            seen.add(match)

    # Limit to the requested number of suggestions
    return suggestions[:limit]


def _get_close_matches(
    token_text: str, candidates: list[str] | set[str], *, limit: int = 3
) -> list[str]:
    """
    Get close matches for token_text from candidates using difflib.

    Uses a sensible cutoff to avoid noisy suggestions.

    Args:
        token_text: The text to find matches for.
        candidates: List or set of candidate strings.
        limit: Maximum number of matches to return.

    Returns:
        List of close matches, ordered by similarity.
    """
    if not candidates:
        return []

    # Use a sensible cutoff: 0.6 for reasonable suggestions
    cutoff = 0.6
    matches = difflib.get_close_matches(token_text, candidates, n=limit, cutoff=cutoff)
    return matches


def _validate_options(
    tokens: list[TokenSpan],
    root_node: JsonObject,
    plugin_name: str,
    action_name: str,
) -> list[DiagnosticIssue]:
    """
    Validate option tokens for a valid command path.

    Only validates tokens that start with '--' (or are '--help'/'-h').

    Args:
        tokens: Option tokens to validate (tokens at index >= 3).
        root_node: The root node from hierarchy.
        plugin_name: The plugin name (token1).
        action_name: The action name (token2).

    Returns:
        List of DiagnosticIssue for option validation problems.
    """
    issues: list[DiagnosticIssue] = []

    # Get the plugin node
    plugin_node = root_node.get(plugin_name)
    if not isinstance(plugin_node, dict):
        # Plugin doesn't exist - should have been caught by token1 validation
        return issues

    # Get the action node
    action_node = plugin_node.get(action_name)
    if not isinstance(action_node, dict):
        # Action doesn't exist - should have been caught by token2 validation
        return issues

    # Get valid options from the action signature
    valid_options = _get_valid_options(action_node)

    # Validate each option token
    for token in tokens:
        token_text = token.text

        # Skip tokens that don't look like options
        if not token_text.startswith("--"):
            # Always treat --help and -h as valid
            if token_text in ("--help", "-h"):
                continue
            # Skip non-option tokens (values, etc.)
            continue

        # Extract option name (handle --opt=value format)
        option_name = token_text
        if "=" in token_text:
            option_name = token_text.split("=", 1)[0]

        # Skip --help and -h
        if option_name in ("--help", "-h"):
            continue

        # Check if option is valid
        if not _is_exact_match(option_name, valid_options):
            # Get suggestions (prefix matches + difflib)
            suggestions = _get_suggestions(option_name, valid_options, limit=3)
            if suggestions:
                message = f"Unknown option '{option_name}'. Did you mean {', '.join(repr(s) for s in suggestions)}?"
            else:
                message = f"Unknown option '{option_name}'."

            issues.append(
                DiagnosticIssue(
                    message=message,
                    start=token.start,
                    end=token.end,
                    code="q2lsp-dni/unknown-option",
                )
            )

    return issues


def _get_valid_options(action_node: JsonObject) -> list[str]:
    """
    Extract valid option labels from action node signature.

    Uses qiime_option_prefix and format_qiime_option_label to format
    option labels consistently with completions.

    Args:
        action_node: The action node containing a signature.

    Returns:
        List of valid option labels (e.g., ['--i-table', '--m-metadata-file']).
    """
    valid_options: list[str] = []

    # Get signature
    signature = action_node.get("signature")
    if signature is None:
        return valid_options

    # Handle real format: list of parameter dicts with signature_type
    if isinstance(signature, list):
        for param in signature:
            if not isinstance(param, dict):
                continue

            param_name = param.get("name")
            if not isinstance(param_name, str):
                continue

            # Get the option prefix (e.g., 'i' for inputs)
            prefix = qiime_option_prefix(param)

            # Format the option label
            option_label = format_qiime_option_label(prefix, param_name)
            valid_options.append(option_label)

        return valid_options

    # Handle legacy format: dict with grouped arrays (backward compatibility)
    if isinstance(signature, dict):
        for param_type in ["inputs", "outputs", "parameters", "metadata"]:
            params = signature.get(param_type)
            if not isinstance(params, list):
                continue

            for param in params:
                if not isinstance(param, dict):
                    continue

                param_name = param.get("name")
                if not isinstance(param_name, str):
                    continue

                # Get the option prefix (e.g., 'i' for inputs)
                prefix = qiime_option_prefix(param)

                # Format the option label
                option_label = format_qiime_option_label(prefix, param_name)
                valid_options.append(option_label)

    return valid_options
