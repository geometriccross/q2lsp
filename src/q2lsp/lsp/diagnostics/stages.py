from collections.abc import Mapping, Sequence

from q2lsp.lsp.diagnostics import codes
from q2lsp.lsp.diagnostics.diagnostic_issue import DiagnosticIssue
from q2lsp.lsp.diagnostics.matching import (
    _get_suggestions,
    _is_exact_match,
)
from q2lsp.lsp.types import TokenSpan
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.options import (
    format_qiime_option_label,
    group_option_tokens,
    normalize_option_to_param_name,
    OptionGroup,
    param_is_required,
)
from q2lsp.qiime.signature_params import (
    get_all_option_labels,
    iter_signature_params,
)
from q2lsp.qiime.types import JsonObject


def _validate_plugin_or_builtin_with_catalog(
    token: TokenSpan, catalog: QiimeCatalog
) -> DiagnosticIssue | None:
    token_text = token.text
    valid_plugins, valid_builtins = catalog.valid_plugins_and_builtins()
    all_valid_names = list(valid_plugins | valid_builtins)

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

    if catalog.command_node(plugin_name) is None:
        return None

    if catalog.is_builtin_leaf(plugin_name):
        return None

    valid_actions = catalog.valid_actions(plugin_name)

    if _is_exact_match(token_text, valid_actions):
        return None

    code = (
        codes.UNKNOWN_SUBCOMMAND
        if catalog.is_builtin(plugin_name)
        else codes.UNKNOWN_ACTION
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


def _validate_options_for_action(
    tokens: list[TokenSpan], action_node: JsonObject
) -> tuple[list[DiagnosticIssue], dict[str, list[str]]]:
    issues: list[DiagnosticIssue] = []
    unknown_option_suggestions: dict[str, list[str]] = {}

    # Get valid options from the action signature
    valid_options = get_all_option_labels(action_node)

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


def _validate_options_with_catalog(
    tokens: list[TokenSpan],
    catalog: QiimeCatalog,
    plugin_name: str,
    action_name: str,
) -> tuple[list[DiagnosticIssue], dict[str, list[str]]]:
    """Validate option tokens for a catalog-backed valid command path."""
    action_node = catalog.action_node(plugin_name, action_name)
    if action_node is None:
        return [], {}

    return _validate_options_for_action(tokens, action_node)


def _validate_required_options_for_action(
    tokens: list[TokenSpan],
    action_node: JsonObject,
    unknown_option_suggestions: Mapping[str, Sequence[str]],
) -> list[DiagnosticIssue]:
    issues: list[DiagnosticIssue] = []

    if len(tokens) < 3:
        return issues

    option_tokens = tokens[3:]
    option_groups = group_option_tokens(option_tokens, lambda token: token.text)

    if _has_help_invocation(option_tokens, option_groups, action_node):
        return issues

    present_param_names: set[str] = set()
    for option in option_groups:
        param_name = normalize_option_to_param_name(option.option_text)
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


def _validate_required_options_with_catalog(
    tokens: list[TokenSpan],
    catalog: QiimeCatalog,
    plugin_name: str,
    action_name: str,
    unknown_option_suggestions: Mapping[str, Sequence[str]],
) -> list[DiagnosticIssue]:
    """Validate required options for a catalog-backed valid command path."""
    action_node = catalog.action_node(plugin_name, action_name)
    if action_node is None:
        return []

    return _validate_required_options_for_action(
        tokens, action_node, unknown_option_suggestions
    )
