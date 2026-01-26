"""Tests for hierarchy_provider module."""

from __future__ import annotations

import threading
import time

import pytest

from q2lsp.qiime.hierarchy_provider import (
    default_hierarchy_provider,
    make_cached_hierarchy_provider,
)
from q2lsp.qiime.types import CommandHierarchy


class TestMakeCachedHierarchyProvider:
    """Tests for make_cached_hierarchy_provider function."""

    def test_builder_called_only_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Builder is called only once even when provider is called multiple times."""
        build_calls = 0

        def mock_builder() -> CommandHierarchy:
            nonlocal build_calls
            build_calls += 1
            return {"test": {}}

        provider = make_cached_hierarchy_provider(mock_builder)

        # Call provider multiple times
        _ = provider()
        _ = provider()
        _ = provider()

        assert build_calls == 1

    def test_returns_same_instance(self) -> None:
        """Same instance is returned on subsequent calls."""
        hierarchy: CommandHierarchy = {"test": {}}

        def mock_builder() -> CommandHierarchy:
            return hierarchy

        provider = make_cached_hierarchy_provider(mock_builder)

        result1 = provider()
        result2 = provider()

        assert result1 is result2

    @pytest.mark.parametrize(
        "expected_hierarchy,description",
        [
            ({"root": {}}, "empty root"),
            ({"qiime": {"builtins": []}}, "root with builtins"),
            (
                {"qiime": {"plugin1": {"actions": {}}, "builtins": []}},
                "root with plugin",
            ),
            ({"root": {"key1": {}, "key2": {}}}, "root with multiple keys"),
        ],
    )
    def test_with_different_builder_return_values(
        self, expected_hierarchy: CommandHierarchy, description: str
    ) -> None:
        """Works with different builder return values."""

        def builder(h: CommandHierarchy = expected_hierarchy) -> CommandHierarchy:
            return h

        provider = make_cached_hierarchy_provider(builder)
        result = provider()

        assert result == expected_hierarchy, f"Failed for: {description}"

    def test_returns_callable_provider(self) -> None:
        """make_cached_hierarchy_provider returns a callable provider."""

        def mock_builder() -> CommandHierarchy:
            return {}

        provider = make_cached_hierarchy_provider(mock_builder)

        assert callable(provider)

    def test_provider_returns_command_hierarchy_structure(self) -> None:
        """Provider returns CommandHierarchy structure."""

        def mock_builder() -> CommandHierarchy:
            return {"qiime": {"builtins": []}}

        provider = make_cached_hierarchy_provider(mock_builder)
        result = provider()

        assert isinstance(result, dict)
        # Check it's a valid CommandHierarchy (str -> dict)
        for key, value in result.items():
            assert isinstance(key, str)
            assert isinstance(value, dict)


class TestDefaultHierarchyProvider:
    """Tests for default_hierarchy_provider function."""

    def test_returns_callable_provider(self) -> None:
        """default_hierarchy_provider returns a callable."""
        provider = default_hierarchy_provider()

        assert callable(provider)

    def test_provider_returns_command_hierarchy_structure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider returns CommandHierarchy structure."""
        # Mock build_qiime_hierarchy to avoid expensive q2cli import
        mock_hierarchy: CommandHierarchy = {"qiime": {"builtins": []}}

        from q2lsp.qiime import hierarchy_provider as hp_module

        monkeypatch.setattr(hp_module, "build_qiime_hierarchy", lambda: mock_hierarchy)

        provider = default_hierarchy_provider()
        result = provider()

        assert isinstance(result, dict)
        # Check it's a valid CommandHierarchy (str -> dict)
        for key, value in result.items():
            assert isinstance(key, str)
            assert isinstance(value, dict)

    def test_provider_is_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default provider uses caching."""
        # Mock build_qiime_hierarchy to track calls
        build_calls = 0

        def mock_build() -> CommandHierarchy:
            nonlocal build_calls
            build_calls += 1
            return {"qiime": {"builtins": []}}

        from q2lsp.qiime import hierarchy_provider as hp_module

        monkeypatch.setattr(hp_module, "build_qiime_hierarchy", mock_build)

        provider = default_hierarchy_provider()

        # Call multiple times
        provider()
        provider()
        provider()

        assert build_calls == 1, "Builder should be called only once due to caching"


class TestThreadSafety:
    """Tests for thread-safe cache behavior."""

    def test_concurrent_calls_build_once(self) -> None:
        """Multiple threads calling provider simultaneously result in exactly one build.

        This test is deterministic by using a Barrier to ensure all threads
        attempt to build at the same time, and tracking call counts precisely.
        """
        build_calls = 0
        build_lock = threading.Lock()
        # Track which threads actually entered the build phase
        build_threads: set[int] = set()
        num_threads = 5

        def mock_builder() -> CommandHierarchy:
            nonlocal build_calls
            with build_lock:
                build_calls += 1
                build_threads.add(threading.get_ident())
                # Simulate expensive operation to increase race condition likelihood
                time.sleep(0.01)
            return {"qiime": {"builtins": []}}

        provider = make_cached_hierarchy_provider(mock_builder)

        # Barrier to synchronize all threads to start at the same time
        barrier = threading.Barrier(num_threads)
        results: list[CommandHierarchy] = []

        def worker() -> None:
            # Wait for all threads to be ready
            barrier.wait()
            # Then all threads call provider simultaneously
            result = provider()
            results.append(result)

        # Start all threads
        threads = [
            threading.Thread(target=worker, daemon=True) for _ in range(num_threads)
        ]
        for t in threads:
            t.start()
        # Join with timeout to prevent deadlocks in test failures
        for t in threads:
            t.join(timeout=5.0)
            assert not t.is_alive(), f"Thread {t.name} timed out (potential deadlock)"

        # Verify exactly one build occurred
        assert build_calls == 1, (
            f"Expected builder to be called exactly once, but was called {build_calls} "
            f"times by threads {build_threads}"
        )
        # Verify all threads got a result
        assert len(results) == num_threads
        # Verify all results are the same instance
        for result in results[1:]:
            assert result is results[0], (
                "All threads should get the same cached instance"
            )

    def test_sequential_calls_still_cached(self) -> None:
        """Sequential calls from different threads still use cache after first build."""
        build_calls = 0

        def mock_builder() -> CommandHierarchy:
            nonlocal build_calls
            build_calls += 1
            return {"qiime": {"builtins": []}}

        provider = make_cached_hierarchy_provider(mock_builder)

        # Call from different threads sequentially
        results: list[CommandHierarchy] = []

        def worker() -> None:
            result = provider()
            results.append(result)

        threads = [threading.Thread(target=worker, daemon=True) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # All calls should use the same cached result
        assert build_calls == 1
        assert len(results) == 3
        for result in results[1:]:
            assert result is results[0]
