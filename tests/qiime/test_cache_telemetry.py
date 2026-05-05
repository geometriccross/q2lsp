"""Tests for cache telemetry in hierarchy_provider."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest

from q2lsp.qiime.hierarchy_provider import make_cached_hierarchy_provider
from q2lsp.qiime.types import CommandHierarchy

LOGGER_NAME = "q2lsp.qiime.hierarchy_provider"


@pytest.fixture(autouse=True)
def isolate_q2lsp_logging() -> Iterator[None]:
    """Let caplog capture q2lsp records regardless of prior logging setup."""
    logger = logging.getLogger("q2lsp")
    original_handlers = list(logger.handlers)
    original_level = logger.level
    original_propagate = logger.propagate

    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)
    logger.propagate = True

    yield

    logger.handlers.clear()
    logger.handlers.extend(original_handlers)
    logger.setLevel(original_level)
    logger.propagate = original_propagate


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

        with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
            result = provider()

        assert result == {"qiime": {"builtins": []}}
        assert build_calls == 1

        assert caplog.record_tuples == [
            (LOGGER_NAME, logging.DEBUG, "Hierarchy cache miss - building hierarchy"),
        ]

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

        with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
            result = provider()

        assert result == {"qiime": {"builtins": []}}
        assert build_calls == 1  # Still only called once

        assert caplog.record_tuples == [
            (LOGGER_NAME, logging.DEBUG, "Hierarchy cache hit - using cached hierarchy"),
        ]
