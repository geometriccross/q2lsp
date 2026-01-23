"""Integration tests for completion logic with real QIIME2 hierarchy.

These tests verify that get_completions() works correctly with actual QIIME2
command data, not mocks. They help catch issues where mock structure diverges
from real QIIME2 CLI output.

Run with: pytest tests/integration/ -v
Skip slow tests: pytest -m "not slow"
"""

from __future__ import annotations

import pytest

# Skip entire module if QIIME2 is not available
qiime2 = pytest.importorskip("qiime2")
q2cli = pytest.importorskip("q2cli")

from q2cli.commands import RootCommand

from q2lsp.qiime.command_hierarchy import build_command_hierarchy
from q2lsp.lsp.completions import get_completions, _COMMAND_METADATA_KEYS
from q2lsp.lsp.types import CompletionContext, ParsedCommand, TokenSpan

# Mark all tests in this module as slow
pytestmark = pytest.mark.slow


# --- Fixtures ---


@pytest.fixture(scope="session")
def qiime_hierarchy() -> dict:
    """Build real QIIME2 hierarchy.

    Session-scoped to avoid rebuilding for each test (expensive).
    """
    try:
        root = RootCommand()
        hierarchy = build_command_hierarchy(root)
    except Exception as e:
        pytest.skip(f"QIIME2 hierarchy unavailable: {e}")

    if "qiime" not in hierarchy:
        pytest.skip("QIIME2 hierarchy missing 'qiime' root node")

    return hierarchy


@pytest.fixture(scope="session")
def qiime_root_node(qiime_hierarchy: dict) -> dict:
    """Return the root node from hierarchy."""
    return qiime_hierarchy["qiime"]


@pytest.fixture(scope="session")
def real_plugin_with_actions(qiime_root_node: dict) -> str:
    """Find a real plugin that has actions.

    Prefers known plugins, falls back to any available.
    """
    builtins = set(qiime_root_node.get("builtins", []))
    preferred = ["diversity", "feature-table", "demux", "phylogeny"]

    # Try preferred plugins first
    for plugin in preferred:
        if plugin in qiime_root_node and plugin not in builtins:
            node = qiime_root_node[plugin]
            if isinstance(node, dict) and _has_actions(node):
                return plugin

    # Fall back to any plugin with actions
    for key, value in qiime_root_node.items():
        if key in builtins:
            continue
        if key in {"name", "help", "short_help", "builtins"}:
            continue
        if isinstance(value, dict) and _has_actions(value):
            return key

    pytest.skip("No plugins with actions found in QIIME2 installation")


@pytest.fixture(scope="session")
def real_action_with_signature(
    qiime_root_node: dict,
    real_plugin_with_actions: str,
) -> tuple[str, str, dict]:
    """Find a real action that has signature parameters.

    Returns (plugin_name, action_name, first_param_dict).
    """
    plugin_node = qiime_root_node[real_plugin_with_actions]

    for action_name, action_node in plugin_node.items():
        if action_name in _COMMAND_METADATA_KEYS:
            continue
        if not isinstance(action_node, dict):
            continue

        signature = action_node.get("signature", [])
        if isinstance(signature, list) and len(signature) > 0:
            first_param = signature[0]
            if isinstance(first_param, dict) and "name" in first_param:
                return (real_plugin_with_actions, action_name, first_param)

    pytest.skip(f"No action with signature found in plugin {real_plugin_with_actions}")


# --- Helper Functions ---


def _has_actions(node: dict) -> bool:
    """Check if a command node has any actions."""
    for key, value in node.items():
        if key in _COMMAND_METADATA_KEYS:
            continue
        if isinstance(value, dict):
            return True
    return False


def _make_root_context(prefix: str = "") -> CompletionContext:
    """Create completion context for root level (qiime <cursor>)."""
    tokens = [TokenSpan("qiime", 0, 5)]
    cmd = ParsedCommand(tokens=tokens, start=0, end=6)
    return CompletionContext(
        mode="root",
        command=cmd,
        current_token=None,
        token_index=1,
        prefix=prefix,
    )


def _make_plugin_context(plugin_name: str, prefix: str = "") -> CompletionContext:
    """Create completion context for plugin level (qiime <plugin> <cursor>)."""
    tokens = [
        TokenSpan("qiime", 0, 5),
        TokenSpan(plugin_name, 6, 6 + len(plugin_name)),
    ]
    cmd = ParsedCommand(tokens=tokens, start=0, end=7 + len(plugin_name))
    return CompletionContext(
        mode="plugin",
        command=cmd,
        current_token=None,
        token_index=2,
        prefix=prefix,
    )


def _make_parameter_context(
    plugin_name: str,
    action_name: str,
    prefix: str = "--",
) -> CompletionContext:
    """Create completion context for parameter level."""
    tokens = [
        TokenSpan("qiime", 0, 5),
        TokenSpan(plugin_name, 6, 6 + len(plugin_name)),
        TokenSpan(
            action_name, 7 + len(plugin_name), 8 + len(plugin_name) + len(action_name)
        ),
    ]
    cmd = ParsedCommand(
        tokens=tokens,
        start=0,
        end=9 + len(plugin_name) + len(action_name),
    )
    return CompletionContext(
        mode="parameter",
        command=cmd,
        current_token=None,
        token_index=3,
        prefix=prefix,
    )


# --- Integration Tests ---


class TestRootCompletion:
    """Test root-level completion with real QIIME2 data."""

    def test_root_completion_includes_known_builtins(
        self, qiime_hierarchy: dict
    ) -> None:
        """Root completion should return known builtin commands."""
        ctx = _make_root_context()
        items = get_completions(ctx, qiime_hierarchy)
        labels = {item.label for item in items}

        # These builtins should exist in any QIIME2 installation
        expected_builtins = {"info", "tools"}
        assert expected_builtins <= labels, (
            f"Missing builtins: {expected_builtins - labels}"
        )

    def test_root_completion_includes_plugins(
        self,
        qiime_hierarchy: dict,
        qiime_root_node: dict,
    ) -> None:
        """Root completion should also return plugins (not just builtins)."""
        ctx = _make_root_context()
        items = get_completions(ctx, qiime_hierarchy)
        labels = {item.label for item in items}

        builtins = set(qiime_root_node.get("builtins", []))
        non_builtin_labels = labels - builtins

        assert len(non_builtin_labels) >= 1, (
            "Expected at least one plugin in completions"
        )

    def test_root_completion_filters_by_prefix(
        self,
        qiime_hierarchy: dict,
        qiime_root_node: dict,
    ) -> None:
        """Root completion with prefix should only return matching items."""
        # Get all labels without prefix
        ctx_all = _make_root_context(prefix="")
        all_items = get_completions(ctx_all, qiime_hierarchy)
        all_labels = {item.label for item in all_items}

        # Find a prefix that will filter results (first char of a known label)
        # Use 'i' for 'info' which should exist
        ctx_filtered = _make_root_context(prefix="i")
        filtered_items = get_completions(ctx_filtered, qiime_hierarchy)
        filtered_labels = {item.label for item in filtered_items}

        # All filtered labels should start with 'i'
        assert all(label.startswith("i") for label in filtered_labels)
        # Filtered should be subset of all
        assert filtered_labels <= all_labels
        # Filtered should have fewer items (unless all start with 'i')
        assert len(filtered_labels) <= len(all_labels)


class TestPluginCompletion:
    """Test plugin-level completion with real QIIME2 data."""

    def test_plugin_completion_returns_actions(
        self,
        qiime_hierarchy: dict,
        qiime_root_node: dict,
        real_plugin_with_actions: str,
    ) -> None:
        """Plugin completion should return action names."""
        ctx = _make_plugin_context(real_plugin_with_actions)
        items = get_completions(ctx, qiime_hierarchy)
        labels = {item.label for item in items}

        # Get expected actions from the plugin node
        plugin_node = qiime_root_node[real_plugin_with_actions]
        expected_actions = {
            k
            for k, v in plugin_node.items()
            if k not in _COMMAND_METADATA_KEYS and isinstance(v, dict)
        }

        # At least one action should be returned
        matching = labels & expected_actions
        assert len(matching) >= 1, (
            f"No actions found for plugin {real_plugin_with_actions}"
        )


class TestBuiltinCompletion:
    """Test builtin command completion with real QIIME2 data."""

    @pytest.mark.parametrize("builtin", ["tools", "types", "metadata", "dev"])
    def test_builtin_commands_return_subcommands(
        self,
        qiime_hierarchy: dict,
        qiime_root_node: dict,
        builtin: str,
    ) -> None:
        """Builtin commands with subcommands should return them."""
        builtins_list = qiime_root_node.get("builtins", [])

        if builtin not in builtins_list:
            pytest.skip(
                f"Builtin '{builtin}' not available in this QIIME2 installation"
            )

        builtin_node = qiime_root_node.get(builtin)
        if not isinstance(builtin_node, dict):
            pytest.skip(f"Builtin '{builtin}' has no node data")

        # Get expected subcommands
        expected_subcommands = {
            k
            for k, v in builtin_node.items()
            if k not in _COMMAND_METADATA_KEYS and isinstance(v, dict)
        }

        if not expected_subcommands:
            pytest.skip(f"Builtin '{builtin}' has no subcommands in this QIIME2 build")

        ctx = _make_plugin_context(builtin)
        items = get_completions(ctx, qiime_hierarchy)
        labels = {item.label for item in items}

        # Should return subcommands, not just --help
        matching = labels & expected_subcommands
        assert len(matching) >= 1, f"Builtin '{builtin}' should return subcommands"
        assert labels != {"--help"}, f"Builtin '{builtin}' returned only --help"


class TestParameterCompletion:
    """Test parameter-level completion with real QIIME2 data."""

    def test_parameter_completion_includes_signature_params(
        self,
        qiime_hierarchy: dict,
        real_action_with_signature: tuple[str, str, dict],
    ) -> None:
        """Parameter completion should return signature parameters."""
        plugin, action, first_param = real_action_with_signature

        ctx = _make_parameter_context(plugin, action)
        items = get_completions(ctx, qiime_hierarchy)
        labels = {item.label for item in items}

        # Expected option name (kebab-case)
        param_name = first_param["name"]
        expected_option = f"--{param_name.replace('_', '-')}"

        assert expected_option in labels, f"Expected '{expected_option}' in completions"
        assert len(labels) >= 2, "Expected at least 2 completion items (param + --help)"

    def test_parameter_completion_excludes_used_params(
        self,
        qiime_hierarchy: dict,
        real_action_with_signature: tuple[str, str, dict],
    ) -> None:
        """Parameter completion should exclude already used parameters."""
        plugin, action, first_param = real_action_with_signature

        # Get all parameters first
        ctx = _make_parameter_context(plugin, action)
        all_items = get_completions(ctx, qiime_hierarchy)
        all_labels = {item.label for item in all_items}

        # The first param should be in completions
        param_name = first_param["name"]
        expected_option = f"--{param_name.replace('_', '-')}"
        assert expected_option in all_labels, (
            f"Expected '{expected_option}' in initial completions"
        )

        # Now create context with that param already used
        used_param_token = TokenSpan(expected_option, 100, 100 + len(expected_option))
        tokens = [
            TokenSpan("qiime", 0, 5),
            TokenSpan(plugin, 6, 6 + len(plugin)),
            TokenSpan(action, 7 + len(plugin), 8 + len(plugin) + len(action)),
            used_param_token,
            TokenSpan("value", 110, 115),  # param value
        ]
        cmd = ParsedCommand(tokens=tokens, start=0, end=115)
        ctx_with_used = CompletionContext(
            mode="parameter",
            command=cmd,
            current_token=None,
            token_index=5,
            prefix="--",
        )

        items_after = get_completions(ctx_with_used, qiime_hierarchy)
        labels_after = {item.label for item in items_after}

        # The used param should NOT be in completions anymore
        assert expected_option not in labels_after, (
            f"'{expected_option}' should be excluded after use"
        )
