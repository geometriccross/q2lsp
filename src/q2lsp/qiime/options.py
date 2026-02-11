from __future__ import annotations

from q2lsp.qiime.types import JsonObject, JsonValue

_QIIME_PREFIXES = ("input", "output", "parameter", "metadata")
_PREFIX_MAP = {"input": "i", "output": "o", "parameter": "p", "metadata": "m"}


def param_is_required(param: JsonObject) -> bool:
    """Determine if a parameter is required.

    Checks explicit ``required`` flag first (used by builtin commands).
    Falls back to the Phase 1 heuristic for plugin actions: ``signature_type``
    present as a string AND ``default`` key absent.
    """
    explicit = param.get("required")
    if isinstance(explicit, bool):
        return explicit

    signature_type = param.get("signature_type")
    return isinstance(signature_type, str) and "default" not in param


def qiime_option_prefix(param: dict[str, JsonValue]) -> str:
    prefix_source = param.get("signature_type") or param.get("type")
    if isinstance(prefix_source, str):
        lower = prefix_source.lower()
        for key in _QIIME_PREFIXES:
            if lower.startswith(key):
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
