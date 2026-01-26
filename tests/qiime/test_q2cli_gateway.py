"""Tests for q2cli gateway module."""

from __future__ import annotations

import logging

import pytest

from q2lsp.qiime.q2cli_gateway import Q2CliGateway, build_qiime_hierarchy_via_gateway
from q2lsp.qiime.types import CommandHierarchy


class TestBuildQIimeHierarchyViaGateway:
    """Tests for build_qiime_hierarchy_via_gateway function."""

    def test_returns_command_hierarchy_structure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns a valid CommandHierarchy structure."""
        # Mock RootCommand and build_command_hierarchy to avoid q2cli import
        mock_root = type(
            "MockRoot", (), {"name": "qiime", "help": "Test help", "short_help": "Test"}
        )
        mock_hierarchy: CommandHierarchy = {"qiime": {"builtins": []}}

        def mock_build_cmd_hierarchy(root: object) -> CommandHierarchy:
            return mock_hierarchy

        monkeypatch.setattr(
            "q2lsp.qiime.q2cli_gateway.RootCommand",
            lambda: mock_root(),
        )
        monkeypatch.setattr(
            "q2lsp.qiime.q2cli_gateway.build_command_hierarchy",
            mock_build_cmd_hierarchy,
        )

        result = build_qiime_hierarchy_via_gateway()

        assert isinstance(result, dict)
        for key, value in result.items():
            assert isinstance(key, str)
            assert isinstance(value, dict)

    def test_delegates_to_build_command_hierarchy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Delegates to build_command_hierarchy with RootCommand instance."""
        mock_root = type("MockRoot", (), {"name": "qiime"})
        received_root = None

        def mock_build_cmd_hierarchy(root: object) -> CommandHierarchy:
            nonlocal received_root
            received_root = root
            return {"qiime": {"builtins": []}}

        monkeypatch.setattr(
            "q2lsp.qiime.q2cli_gateway.RootCommand",
            lambda: mock_root(),
        )
        monkeypatch.setattr(
            "q2lsp.qiime.q2cli_gateway.build_command_hierarchy",
            mock_build_cmd_hierarchy,
        )

        build_qiime_hierarchy_via_gateway()

        assert received_root is not None
        assert received_root.name == "qiime"


class TestQ2CliGateway:
    """Tests for Q2CliGateway class."""

    def test_build_hierarchy_returns_hierarchy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """build_hierarchy returns a CommandHierarchy."""
        mock_hierarchy: CommandHierarchy = {"qiime": {"builtins": []}}

        gateway = Q2CliGateway(logger=logging.getLogger("test"))
        monkeypatch.setattr(gateway, "_build_hierarchy_impl", lambda: mock_hierarchy)

        result = gateway.build_hierarchy()

        assert result == mock_hierarchy

    def test_build_hierarchy_logs_start_and_end(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """build_hierarchy logs start and end events."""
        mock_hierarchy: CommandHierarchy = {"qiime": {"builtins": []}}
        gateway = Q2CliGateway(logger=logging.getLogger("test"))

        monkeypatch.setattr(gateway, "_build_hierarchy_impl", lambda: mock_hierarchy)

        with caplog.at_level(logging.DEBUG):
            result = gateway.build_hierarchy()

        assert result == mock_hierarchy

        # Check for log messages about build start and end
        log_messages = [record.message for record in caplog.records]
        assert any("hierarchy build" in msg.lower() for msg in log_messages)
        assert any("completed successfully" in msg.lower() for msg in log_messages)

    def test_build_hierarchy_logs_error_on_failure(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """build_hierarchy logs error when build fails."""
        gateway = Q2CliGateway(logger=logging.getLogger("test"))

        def failing_impl() -> CommandHierarchy:
            raise RuntimeError("Build failed")

        monkeypatch.setattr(gateway, "_build_hierarchy_impl", failing_impl)

        with pytest.raises(RuntimeError, match="Build failed"):
            with caplog.at_level(logging.ERROR):
                gateway.build_hierarchy()

        # Check for error log
        error_logs = [
            record for record in caplog.records if record.levelno >= logging.ERROR
        ]
        assert len(error_logs) > 0
        assert "failed" in error_logs[0].message.lower()

    def test_build_hierarchy_includes_duration_in_log(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """build_hierarchy logs duration information."""
        mock_hierarchy: CommandHierarchy = {"qiime": {"builtins": []}}
        gateway = Q2CliGateway(logger=logging.getLogger("test"))

        monkeypatch.setattr(gateway, "_build_hierarchy_impl", lambda: mock_hierarchy)

        with caplog.at_level(logging.DEBUG):
            gateway.build_hierarchy()

        # Check for duration in log messages
        log_messages = [record.message for record in caplog.records]
        assert any(
            "duration" in msg.lower() or "ms" in msg.lower() for msg in log_messages
        )
