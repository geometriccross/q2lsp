"""Shared synchronous handler error policy."""

from __future__ import annotations

import logging

import pytest

from q2lsp.lsp.error_handling import wrap_handler


def test_handler_forwards_arguments_and_preserves_metadata() -> None:
    @wrap_handler(
        logger=logging.getLogger("q2lsp.test"),
        feature_name="test/feature",
        default_factory=lambda: "default",
    )
    def handler(first: str, *, second: str) -> str:
        """Handler documentation."""
        return f"{first}:{second}"

    assert handler("arg", second="kwarg") == "arg:kwarg"
    assert handler.__name__ == "handler"
    assert handler.__doc__ == "Handler documentation."


def test_default_factory_is_only_called_on_failure() -> None:
    calls = 0

    def default_factory() -> str:
        nonlocal calls
        calls += 1
        return "default"

    @wrap_handler(
        logger=logging.getLogger("q2lsp.test"),
        feature_name="test/feature",
        default_factory=default_factory,
    )
    def handler(fail: bool) -> str:
        if fail:
            raise ValueError("test error")
        return "success"

    assert handler(False) == "success"
    assert calls == 0
    assert handler(True) == "default"
    assert calls == 1


def test_failure_logs_exception(caplog: pytest.LogCaptureFixture) -> None:
    @wrap_handler(
        logger=logging.getLogger("q2lsp.test"),
        feature_name="test/feature",
        default_factory=lambda: None,
    )
    def handler() -> None:
        raise ValueError("specific error message")

    with caplog.at_level(logging.ERROR):
        assert handler() is None

    record = caplog.records[-1]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert "test/feature" in record.getMessage()
    assert "specific error message" in caplog.text
