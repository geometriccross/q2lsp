"""Contract tests to verify real QIIME2 hierarchy matches completion expectations.

These tests build the actual QIIME2 command hierarchy and verify that it conforms
to the structure expected by the completion logic. They help catch:
- Missing metadata keys in skip lists
- Unexpected action shapes
- Schema drift between QIIME2 versions

Run with: pytest tests/contract/ -v
Skip in CI without QIIME2: tests will auto-skip if qiime2/q2cli not installed
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

import pytest

# Skip entire module if QIIME2 is not available
qiime2 = pytest.importorskip("qiime2")
q2cli = pytest.importorskip("q2cli")

from q2cli.commands import RootCommand

from q2lsp.qiime.command_hierarchy import build_command_hierarchy
from q2lsp.lsp.completions import _ROOT_METADATA_KEYS, _COMMAND_METADATA_KEYS

JsonValue = Any
JsonObject = dict[str, JsonValue]


# --- Helper Functions ---


def is_action_node(node: Mapping[str, JsonValue]) -> bool:
    """Return True if node looks like an action for completion purposes.

    An action node should have either 'description' or 'signature'.
    """
    if not isinstance(node, dict):
        return False
    return "description" in node or "signature" in node


def iter_command_nodes(
    root_node: Mapping[str, JsonValue],
) -> Iterator[tuple[str, Mapping[str, JsonValue]]]:
    """Yield (command_name, command_node) for each plugin and builtin.

    Excludes root metadata keys and the 'builtins' list itself.
    """
    for key, value in root_node.items():
        if key in _ROOT_METADATA_KEYS:
            continue
        if isinstance(value, dict):
            yield key, value


def iter_action_entries(
    command_node: Mapping[str, JsonValue],
) -> Iterator[tuple[str, Mapping[str, JsonValue]]]:
    """Yield (action_name, action_node) for keys that completions treats as actions.

    Keys not in _COMMAND_METADATA_KEYS whose values are dict-like and action-shaped.
    """
    for key, value in command_node.items():
        if key in _COMMAND_METADATA_KEYS:
            continue
        if isinstance(value, dict) and is_action_node(value):
            yield key, value


# --- Fixtures ---


@pytest.fixture(scope="session")
def root_node() -> JsonObject:
    """Build real QIIME2 hierarchy and return the root node.

    This fixture is session-scoped to avoid rebuilding the hierarchy
    for each test (plugin discovery is expensive).
    """
    try:
        root = RootCommand()
        hierarchy = build_command_hierarchy(root)
    except Exception as e:
        pytest.skip(f"QIIME2 hierarchy unavailable: {e}")

    if "qiime" not in hierarchy:
        pytest.skip("QIIME2 hierarchy missing 'qiime' root node")

    return hierarchy["qiime"]


# --- Contract Tests ---


class TestBuiltinExistenceContract:
    """Verify every builtin listed in 'builtins' exists as a key in root_node."""

    def test_builtins_key_exists(self, root_node: JsonObject) -> None:
        """Root node must have 'builtins' key."""
        assert "builtins" in root_node
        assert isinstance(root_node["builtins"], list)

    def test_each_builtin_exists_as_key(self, root_node: JsonObject) -> None:
        """Each builtin name must exist as a key in root_node."""
        builtins = root_node.get("builtins", [])
        for builtin_name in builtins:
            assert builtin_name in root_node, (
                f"Builtin '{builtin_name}' not found in root_node"
            )
            assert isinstance(root_node[builtin_name], dict), (
                f"Builtin '{builtin_name}' is not a dict"
            )


class TestActionShapeContract:
    """Verify non-metadata dict keys in command nodes are valid actions."""

    def test_action_nodes_have_required_fields(self, root_node: JsonObject) -> None:
        """Any dict key not in metadata should have 'description' or 'signature'."""
        violations: list[str] = []

        for cmd_name, cmd_node in iter_command_nodes(root_node):
            for key, value in cmd_node.items():
                if key in _COMMAND_METADATA_KEYS:
                    continue
                if isinstance(value, dict):
                    if not is_action_node(value):
                        violations.append(
                            f"{cmd_name}.{key}: missing 'description' or 'signature'"
                        )

        assert not violations, f"Action shape violations:\n" + "\n".join(violations)


class TestSignatureShapeContract:
    """Verify action signatures have proper structure."""

    def test_signature_params_have_name(self, root_node: JsonObject) -> None:
        """Each parameter in signature must have a 'name' field."""
        violations: list[str] = []

        for cmd_name, cmd_node in iter_command_nodes(root_node):
            for action_name, action_node in iter_action_entries(cmd_node):
                signature = action_node.get("signature")
                if signature is None:
                    continue

                if not isinstance(signature, list):
                    violations.append(
                        f"{cmd_name}.{action_name}: signature is not a list"
                    )
                    continue

                for i, param in enumerate(signature):
                    if not isinstance(param, dict):
                        violations.append(
                            f"{cmd_name}.{action_name}.signature[{i}]: not a dict"
                        )
                        continue
                    if "name" not in param:
                        violations.append(
                            f"{cmd_name}.{action_name}.signature[{i}]: missing 'name'"
                        )
                    elif not isinstance(param["name"], str) or not param["name"]:
                        violations.append(
                            f"{cmd_name}.{action_name}.signature[{i}]: 'name' is empty or not str"
                        )

        assert not violations, f"Signature violations:\n" + "\n".join(violations)


class TestMetadataKeysCoverageContract:
    """Verify metadata skip list covers actual metadata keys."""

    def test_no_unknown_metadata_keys(self, root_node: JsonObject) -> None:
        """All metadata keys in hierarchy should be in _COMMAND_METADATA_KEYS."""
        unknown_keys: dict[str, set[str]] = {}

        for cmd_name, cmd_node in iter_command_nodes(root_node):
            # Keys that are NOT actions are metadata
            action_keys = {
                k
                for k, v in cmd_node.items()
                if isinstance(v, dict) and is_action_node(v)
            }
            metadata_keys = set(cmd_node.keys()) - action_keys
            unknown = metadata_keys - _COMMAND_METADATA_KEYS

            if unknown:
                unknown_keys[cmd_name] = unknown

        if unknown_keys:
            msg = "Unknown metadata keys (may be treated as actions):\n"
            for cmd, keys in unknown_keys.items():
                msg += f"  {cmd}: {keys}\n"
            pytest.fail(msg)


class TestNoUnexpectedActionsContract:
    """Verify no metadata key collides with real action names."""

    def test_action_names_disjoint_from_metadata_keys(
        self, root_node: JsonObject
    ) -> None:
        """No action should be named the same as a metadata skip key."""
        collisions: list[str] = []

        for cmd_name, cmd_node in iter_command_nodes(root_node):
            action_names = {
                k
                for k, v in cmd_node.items()
                if isinstance(v, dict) and is_action_node(v)
            }
            collision = action_names & _COMMAND_METADATA_KEYS
            if collision:
                collisions.append(f"{cmd_name}: {collision}")

        assert not collisions, f"Action/metadata key collisions:\n" + "\n".join(
            collisions
        )
