"""Tests for cache telemetry in hierarchy_provider."""

from __future__ import annotations

import logging

import pytest

from q2lsp.qiime.hierarchy_provider import make_cached_hierarchy_provider
from q2lsp.qiime.types import CommandHierarchy


class TestCacheTelemetry:
    """Tests for cache telemetry and logging."""

    def test_logs_cache_miss_on_first_call(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Logs cache miss when hierarchy is not yet cached."""
        build_calls = 0

        def mock_builder() -> CommandHierarchy:
            nonlocal build_calls
            build_calls += 1
            return {"qiime": {"builtins": []}}

        provider = make_cached_hierarchy_provider(mock_builder)

        with caplog.at_level(logging.DEBUG):
            result = provider()

        assert result == {"qiime": {"builtins": []}}
        assert build_calls == 1

        # Check for cache miss log
        log_messages = [record.message for record in caplog.records]
        assert any(
            "cache miss" in msg.lower() or "not cached" in msg.lower()
            for msg in log_messages
        )

    def test_logs_cache_hit_on_subsequent_calls(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Logs cache hit when hierarchy is already cached."""
        build_calls = 0

        def mock_builder() -> CommandHierarchy:
            nonlocal build_calls
            build_calls += 1
            return {"qiime": {"builtins": []}}

        provider = make_cached_hierarchy_provider(mock_builder)

        # First call to populate cache
        provider()

        # Reset caplog for second call
        caplog.clear()

        with caplog.at_level(logging.DEBUG):
            result = provider()

        assert result == {"qiime": {"builtins": []}}
        assert build_calls == 1  # Still only called once

        # Check for cache hit log
        log_messages = [record.message for record in caplog.records]
        assert any(
            "cache hit" in msg.lower() or "using cached" in msg.lower()
            for msg in log_messages
        )
