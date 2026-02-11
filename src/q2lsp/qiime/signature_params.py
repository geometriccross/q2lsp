"""Shared signature parameter query helpers for QIIME action nodes."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from q2lsp.qiime.options import (
    format_qiime_option_label,
    param_is_required,
    qiime_option_prefix,
)
from q2lsp.qiime.types import ActionSignatureParameter, JsonObject


def get_all_option_labels(action_node: JsonObject) -> list[str]:
    """
    Extract valid option labels from action node signature.

    Uses qiime_option_prefix and format_qiime_option_label to format
    option labels consistently with completions.

    Args:
        action_node: The action node containing a signature.

    Returns:
        List of valid option labels (e.g., ['--i-table', '--m-metadata-file']).
    """
    return [
        format_qiime_option_label(prefix, param_name)
        for param_name, prefix, _param in iter_signature_params(action_node)
    ]


def get_required_option_labels(action_node: JsonObject) -> list[str]:
    """Extract required option labels from action node signature."""
    required_options: list[str] = []
    for param_name, prefix, param in iter_signature_params(action_node):
        if param_is_required(param):
            required_options.append(format_qiime_option_label(prefix, param_name))

    return required_options


def iter_signature_params(
    action_node: JsonObject,
) -> Iterator[tuple[str, str, ActionSignatureParameter]]:
    """
    Iterate over signature parameters from an action node.

    Yields (param_name, option_prefix, param_dict) tuples.
    Handles both list format (with signature_type) and legacy dict format.

    Args:
        action_node: The action node containing a signature.

    Yields:
        Tuples of (param_name, option_prefix, param_dict).
    """
    signature = action_node.get("signature")
    if signature is None:
        return

    if isinstance(signature, list):
        for param in signature:
            if not isinstance(param, dict):
                continue
            typed_param = cast(ActionSignatureParameter, param)

            param_name = typed_param.get("name")
            if not isinstance(param_name, str) or not param_name:
                continue

            prefix = qiime_option_prefix(typed_param)
            yield (param_name, prefix, typed_param)
        return

    if isinstance(signature, dict):
        for param_type in ["inputs", "outputs", "parameters", "metadata"]:
            params = signature.get(param_type)
            if not isinstance(params, list):
                continue

            for param in params:
                if not isinstance(param, dict):
                    continue
                typed_param = cast(ActionSignatureParameter, param)

                param_name = typed_param.get("name")
                if not isinstance(param_name, str) or not param_name:
                    continue

                prefix = qiime_option_prefix(typed_param)
                yield (param_name, prefix, typed_param)
