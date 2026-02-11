"""Metadata key constants for filtering command hierarchy nodes.

These frozensets enumerate keys that carry metadata (help text, IDs, etc.)
rather than child commands/actions/plugins in the QIIME 2 hierarchy dict.
"""

from __future__ import annotations

ROOT_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "help",
        "short_help",
        "builtins",
    }
)
"""Keys on the root node that are NOT plugin/builtin entries."""

COMMAND_METADATA_KEYS: frozenset[str] = frozenset(
    {
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
)
"""Keys on a plugin/builtin node that are NOT action entries."""

BUILTIN_NODE_METADATA_KEYS: frozenset[str] = COMMAND_METADATA_KEYS | frozenset(
    {
        "builtins",
    }
)
"""Keys on a builtin node used in leaf-detection (COMMAND_METADATA_KEYS + 'builtins')."""
