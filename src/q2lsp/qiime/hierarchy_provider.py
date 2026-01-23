from __future__ import annotations

from typing import Callable, TypeAlias

from q2lsp.qiime.types import CommandHierarchy

HierarchyBuilder: TypeAlias = Callable[[], CommandHierarchy]
HierarchyProvider: TypeAlias = Callable[[], CommandHierarchy]

__all__ = [
    "HierarchyBuilder",
    "HierarchyProvider",
    "build_qiime_hierarchy",
    "make_cached_hierarchy_provider",
    "default_hierarchy_provider",
]


def build_qiime_hierarchy() -> CommandHierarchy:
    """Build QIIME2 command hierarchy from q2cli (expensive operation)."""
    from q2cli.commands import RootCommand

    from q2lsp.qiime.command_hierarchy import build_command_hierarchy

    root = RootCommand()
    return build_command_hierarchy(root)


def make_cached_hierarchy_provider(builder: HierarchyBuilder) -> HierarchyProvider:
    """Create a cached provider that calls builder once and caches result."""

    cache: CommandHierarchy | None = None

    def provider() -> CommandHierarchy:
        nonlocal cache
        if cache is None:
            cache = builder()
        return cache

    return provider


def default_hierarchy_provider() -> HierarchyProvider:
    """Create the default production hierarchy provider."""
    return make_cached_hierarchy_provider(build_qiime_hierarchy)
