from __future__ import annotations

import threading
from typing import Callable, TypeAlias

from q2lsp.logging import get_logger
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
    from q2lsp.qiime.q2cli_gateway import build_qiime_hierarchy_via_gateway

    return build_qiime_hierarchy_via_gateway()


def make_cached_hierarchy_provider(builder: HierarchyBuilder) -> HierarchyProvider:
    """Create a cached provider that calls builder once and caches result.

    Logs cache misses (first call) and cache hits (subsequent calls).
    Thread-safe: ensures builder is called exactly once even under concurrent access.
    """

    cache: CommandHierarchy | None = None
    _lock = threading.Lock()
    _logger = get_logger("qiime.hierarchy_provider")

    def provider() -> CommandHierarchy:
        nonlocal cache
        # Double-checked locking: check cache without lock first
        if cache is None:
            with _lock:
                # Check again while holding lock
                if cache is None:
                    _logger.debug("Hierarchy cache miss - building hierarchy")
                    cache = builder()
                else:
                    _logger.debug("Hierarchy cache hit - using cached hierarchy")
        else:
            _logger.debug("Hierarchy cache hit - using cached hierarchy")
        return cache

    return provider


def default_hierarchy_provider() -> HierarchyProvider:
    """Create the default production hierarchy provider."""
    return make_cached_hierarchy_provider(build_qiime_hierarchy)
