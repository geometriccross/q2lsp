from collections.abc import Mapping, Sequence

from q2lsp.lsp.diagnostics import codes
from q2lsp.lsp.diagnostics.diagnostic_issue import DiagnosticIssue
from q2lsp.lsp.diagnostics.matching import (
    _get_suggestions,
    _is_exact_match,
)
from q2lsp.lsp.types import TokenSpan
from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.catalog_facts import QiimeOptionFact
from q2lsp.qiime.options import (
    group_option_tokens,
    normalize_option_to_param_name,
    OptionGroup,
)


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
