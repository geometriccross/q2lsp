from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from q2lsp.qiime.types import ActionSignatureParameter

_QIIME_PREFIXES = ("input", "output", "parameter", "metadata")
_PREFIX_MAP = {"input": "i", "output": "o", "parameter": "p", "metadata": "m"}
Q2_SIGNATURE_KINDS = frozenset({"input", "output", "parameter", "metadata", "artifact"})
_QIIME_OPTION_PREFIXES = frozenset({"i", "o", "p", "m"})
_T = TypeVar("_T", covariant=True)


@dataclass(frozen=True)
class OptionGroup(Generic[_T]):
    token: _T
    option_text: str
    value_tokens: tuple[_T, ...] = ()
    inline_value: str | None = None


def split_inline_option_value(token_text: str) -> tuple[str, str | None]:
    option_text, separator, inline_value = token_text.partition("=")
    if not separator:
        return token_text, None
    return option_text, inline_value


def group_option_tokens(
    tokens: Sequence[_T],
    get_text: Callable[[_T], str],
    *,
    start_index: int = 0,
) -> tuple[OptionGroup[_T], ...]:
    grouped: list[OptionGroup[_T]] = []
    current_token: _T | None = None
    current_option_text = ""
    current_value_tokens: list[_T] = []
    current_inline_value: str | None = None

    for token in tokens[start_index:]:
        token_text = get_text(token)
        if token_text.startswith("--"):
            if current_token is not None:
                grouped.append(
                    OptionGroup(
                        token=current_token,
                        option_text=current_option_text,
                        value_tokens=tuple(current_value_tokens),
                        inline_value=current_inline_value,
                    )
                )

            option_text, inline_value = split_inline_option_value(token_text)
            current_token = token
            current_option_text = option_text
            current_value_tokens = []
            current_inline_value = inline_value
            continue

        if current_token is None:
            continue

        current_value_tokens.append(token)

    if current_token is not None:
        grouped.append(
            OptionGroup(
                token=current_token,
                option_text=current_option_text,
                value_tokens=tuple(current_value_tokens),
                inline_value=current_inline_value,
            )
        )

    return tuple(grouped)


def qiime_signature_kind(param: ActionSignatureParameter) -> str | None:
    """Return the QIIME 2 signature kind for a parameter, or None.

    Resolution order:
    1. ``signature_type`` field if present and string.
    2. ``type`` field if present and its lowercase value is a known
       QIIME 2 SDK signature kind.
    3. ``None`` otherwise (e.g. click-native params with type "text"/"path").
    """
    sig = param.get("signature_type")
    if isinstance(sig, str):
        return sig.lower()
    typ = param.get("type")
    if isinstance(typ, str) and typ.lower() in Q2_SIGNATURE_KINDS:
        return typ.lower()
    return None


def param_is_required(param: ActionSignatureParameter) -> bool:
    """Determine if a parameter is required.

    Checks explicit ``required`` flag first (used by builtin commands).
    Falls back to checking for a known QIIME 2 signature kind
    (via ``signature_type`` or ``type``) with no ``default`` key.
    """
    explicit = param.get("required")
    if isinstance(explicit, bool):
        return explicit

    return qiime_signature_kind(param) is not None and "default" not in param


def qiime_option_prefix(param: ActionSignatureParameter) -> str:
    kind = qiime_signature_kind(param)
    if kind is not None:
        for key in _QIIME_PREFIXES:
            if kind.startswith(key):
                return _PREFIX_MAP[key]
    return ""


def format_qiime_option_label(option_prefix: str, name: str) -> str:
    dashed = name.replace("_", "-")
    return f"--{option_prefix + '-' if option_prefix else ''}{dashed}"


def option_label_matches_prefix(option_name: str, prefix_filter: str) -> bool:
    if not prefix_filter:
        return True
    if option_name.startswith(prefix_filter):
        return True
    opt = option_name.lstrip("-")
    pref = prefix_filter.lstrip("-")
    if len(opt) >= 2 and opt[0] in {"i", "o", "p", "m"} and opt[1] == "-":
        opt = opt[2:]
    return opt.startswith(pref)


def normalize_option_to_param_name(token_text: str) -> str | None:
    """Normalize an option token to its canonical signature param name."""
    if not token_text.startswith("--"):
        return None

    option_text, _ = split_inline_option_value(token_text)
    option_name = option_text[2:].lower()
    param_name = option_name.replace("-", "_")

    parts = param_name.split("_", 1)
    if len(parts) == 2 and parts[0] in _QIIME_OPTION_PREFIXES:
        return parts[1]

    return param_name
