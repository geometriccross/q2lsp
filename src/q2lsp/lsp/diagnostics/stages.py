from q2lsp.lsp.diagnostics import codes
from q2lsp.lsp.diagnostics.hierarchy import (
    _get_valid_plugins_and_builtins,
    _get_valid_actions,
    _is_builtin_leaf,
)
from q2lsp.lsp.diagnostics.matching import (
    _is_exact_match,
    _get_suggestions,
    _extract_single_suggestion,
)
from q2lsp.lsp.diagnostics.validator import DiagnosticIssue
from q2lsp.lsp.types import TokenSpan
from q2lsp.qiime.options import (
    format_qiime_option_label,
    normalize_option_to_param_name,
    param_is_required,
)
from q2lsp.qiime.signature_params import (
    get_all_option_labels,
    iter_signature_params,
)
from q2lsp.qiime.types import JsonObject


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
        code=codes.UNKNOWN_ROOT,
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
    code = codes.UNKNOWN_SUBCOMMAND if is_builtin else codes.UNKNOWN_ACTION

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
    valid_options = get_all_option_labels(action_node)

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
                    code=codes.UNKNOWN_OPTION,
                )
            )

    return issues


def _validate_required_options(
    tokens: list[TokenSpan],
    root_node: JsonObject,
    plugin_name: str,
    action_name: str,
    unknown_option_issues: list[DiagnosticIssue],
) -> list[DiagnosticIssue]:
    """Validate required options for an already valid command path."""
    issues: list[DiagnosticIssue] = []

    plugin_node = root_node.get(plugin_name)
    if not isinstance(plugin_node, dict):
        return issues

    action_node = plugin_node.get(action_name)
    if not isinstance(action_node, dict):
        return issues

    if len(tokens) < 3:
        return issues

    option_tokens = tokens[3:]

    # Suppress required-option diagnostics for help invocations.
    for token in option_tokens:
        token_name = token.text.split("=", 1)[0]
        if token_name in ("--help", "-h"):
            return issues

    present_param_names: set[str] = set()
    for token in option_tokens:
        param_name = normalize_option_to_param_name(token.text)
        if param_name is None:
            continue
        present_param_names.add(param_name.lower())

    required_param_options = {
        name.lower(): format_qiime_option_label(option_prefix, name)
        for name, option_prefix, param in iter_signature_params(action_node)
        if param_is_required(param)
    }
    missing_param_options = {
        param_name: option_label
        for param_name, option_label in required_param_options.items()
        if param_name not in present_param_names
    }

    suppressed_missing: set[str] = set()
    for unknown_issue in unknown_option_issues:
        suggestion = _extract_single_suggestion(unknown_issue.message)
        if suggestion is None:
            continue
        suggestion_param_name = normalize_option_to_param_name(suggestion)
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
