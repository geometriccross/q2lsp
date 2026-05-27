"""Shared signature parameter query helpers for QIIME action nodes."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from q2lsp.qiime.signature import qiime_option_prefix
from q2lsp.qiime.types import ActionSignatureParameter, JsonObject


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
