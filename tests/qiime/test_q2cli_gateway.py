"""Tests for q2cli gateway module."""

from __future__ import annotations

import logging

import click
import pytest

from q2lsp.qiime.q2cli_gateway import (
    Q2CliGateway,
    build_qiime_hierarchy_via_gateway,
    create_qiime_help_provider,
)
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


class TestCreateQiimeHelpProvider:
    """Tests for create_qiime_help_provider function."""

    def test_provider_returns_help_for_root_command(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider returns help text for root command (empty path) with correct Usage."""

        # Create a mock click command that uses actual click Context behavior
        class MockRootCommand(click.Command):
            name = "qiime"
            help_text = "QIIME 2 command-line interface"
            short_help = "QIIME 2 CLI"

            def get_help(self, ctx: click.Context) -> str:
                # Use click's built-in help formatting to detect proper context chain
                info_name = ctx.info_name or self.name
                return f"Usage: {info_name} [OPTIONS] COMMAND [ARGS]...\n\n  QIIME 2 command-line interface.\n\nOptions:\n  --help  Show this message and exit.\n"

        monkeypatch.setattr(
            "q2lsp.qiime.q2cli_gateway._get_root_command",
            lambda: MockRootCommand(name="qiime"),
        )

        provider = create_qiime_help_provider(max_content_width=80, color=False)
        help_text = provider([])

        assert help_text is not None
        assert "Usage:" in help_text
        # Verify proper command path formatting
        assert "Usage: qiime" in help_text
        assert "Options:" in help_text

    def test_provider_returns_help_for_subcommand(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider returns help text for subcommand with correct Usage path."""

        # Create mock subcommand that respects parent context
        class MockSubcommand(click.Command):
            name = "info"
            help_text = "Display information about current deployment"
            short_help = "Display deployment info"

            def get_help(self, ctx: click.Context) -> str:
                # Build usage from context chain
                usage_parts = []
                c = ctx
                while c is not None:
                    if c.info_name:
                        usage_parts.append(c.info_name)
                    c = c.parent
                usage = " ".join(reversed(usage_parts)) if usage_parts else "info"
                return f"Usage: {usage} [OPTIONS]\n\n  Display information about current deployment.\n\nOptions:\n  --help  Show this message and exit.\n"

        # Create mock root command with MultiCommand behavior
        class MockRootCommand(click.MultiCommand):
            name = "qiime"
            help_text = "QIIME 2 CLI"
            short_help = "QIIME 2"

            def get_command(
                self, ctx: click.Context, cmd_name: str
            ) -> click.Command | None:
                if cmd_name == "info":
                    return MockSubcommand(name=cmd_name)
                return None

        monkeypatch.setattr(
            "q2lsp.qiime.q2cli_gateway._get_root_command",
            lambda: MockRootCommand(name="qiime"),
        )

        provider = create_qiime_help_provider(max_content_width=80, color=False)
        help_text = provider(["info"])

        assert help_text is not None
        assert "Usage:" in help_text
        # Verify proper command path formatting with parent context
        assert "Usage: qiime info" in help_text
        assert "Display information about current deployment" in help_text

    def test_provider_returns_none_for_invalid_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider returns None for invalid command path."""

        # Create mock root command
        class MockRootCommand(click.MultiCommand):
            name = "qiime"
            help_text = "QIIME 2 CLI"
            short_help = "QIIME 2"

            def get_command(
                self, ctx: click.Context, cmd_name: str
            ) -> click.Command | None:
                # Always return None to simulate invalid command
                return None

        monkeypatch.setattr(
            "q2lsp.qiime.q2cli_gateway._get_root_command",
            lambda: MockRootCommand(name="qiime"),
        )

        provider = create_qiime_help_provider(max_content_width=80, color=False)
        help_text = provider(["invalid-command"])

        assert help_text is None

    def test_provider_uses_specified_max_content_width(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider uses the specified max_content_width when creating Context."""
        max_width_passed = 0

        # Create mock root command
        class MockRootCommand(click.Command):
            name = "qiime"
            help_text = "QIIME 2 CLI"
            short_help = "QIIME 2"

            def get_help(self, ctx: click.Context) -> str:
                nonlocal max_width_passed
                max_width_passed = ctx.max_content_width
                return "Help text"

        monkeypatch.setattr(
            "q2lsp.qiime.q2cli_gateway._get_root_command",
            lambda: MockRootCommand(name="qiime"),
        )

        provider = create_qiime_help_provider(max_content_width=120, color=False)
        provider([])

        assert max_width_passed == 120

    def test_provider_uses_specified_color_setting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider uses the specified color setting when creating Context."""
        color_passed = None

        # Create mock root command
        class MockRootCommand(click.Command):
            name = "qiime"
            help_text = "QIIME 2 CLI"
            short_help = "QIIME 2"

            def get_help(self, ctx: click.Context) -> str:
                nonlocal color_passed
                color_passed = ctx.color
                return "Help text"

        monkeypatch.setattr(
            "q2lsp.qiime.q2cli_gateway._get_root_command",
            lambda: MockRootCommand(name="qiime"),
        )

        provider = create_qiime_help_provider(max_content_width=80, color=True)
        provider([])

        assert color_passed is True

    def test_provider_context_chain_for_tools_command(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider builds proper context chain for nested commands (tools)."""

        class MockToolsCommand(click.Command):
            name = "tools"
            help_text = "QIIME 2 tools"
            short_help = "Tools"

            def get_help(self, ctx: click.Context) -> str:
                # Build usage from context chain
                usage_parts = []
                c = ctx
                while c is not None:
                    if c.info_name:
                        usage_parts.append(c.info_name)
                    c = c.parent
                usage = " ".join(reversed(usage_parts)) if usage_parts else "tools"
                return f"Usage: {usage} [OPTIONS]\n\n  QIIME 2 tools.\n\nOptions:\n  --help  Show this message and exit.\n"

        class MockRootCommand(click.MultiCommand):
            name = "qiime"
            help_text = "QIIME 2 CLI"
            short_help = "QIIME 2"

            def get_command(
                self, ctx: click.Context, cmd_name: str
            ) -> click.Command | None:
                if cmd_name == "tools":
                    return MockToolsCommand(name=cmd_name)
                return None

        monkeypatch.setattr(
            "q2lsp.qiime.q2cli_gateway._get_root_command",
            lambda: MockRootCommand(name="qiime"),
        )

        provider = create_qiime_help_provider(max_content_width=80, color=False)
        help_text = provider(["tools"])

        assert help_text is not None
        # Verify proper command path formatting with parent context
        assert "Usage: qiime tools" in help_text
        assert "QIIME 2 tools" in help_text

    def test_provider_context_chain_for_nested_action(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider builds proper context chain for deeply nested commands (tools export)."""

        class MockExportCommand(click.Command):
            name = "export"
            help_text = "Export data"
            short_help = "Export"

            def get_help(self, ctx: click.Context) -> str:
                # Build usage from context chain
                usage_parts = []
                c = ctx
                while c is not None:
                    if c.info_name:
                        usage_parts.append(c.info_name)
                    c = c.parent
                usage = " ".join(reversed(usage_parts)) if usage_parts else "export"
                return f"Usage: {usage} [OPTIONS]\n\n  Export data.\n\nOptions:\n  --help  Show this message and exit.\n"

        class MockToolsCommand(click.MultiCommand):
            name = "tools"
            help_text = "QIIME 2 tools"
            short_help = "Tools"

            def get_command(
                self, ctx: click.Context, cmd_name: str
            ) -> click.Command | None:
                if cmd_name == "export":
                    return MockExportCommand(name=cmd_name)
                return None

        class MockRootCommand(click.MultiCommand):
            name = "qiime"
            help_text = "QIIME 2 CLI"
            short_help = "QIIME 2"

            def get_command(
                self, ctx: click.Context, cmd_name: str
            ) -> click.Command | None:
                if cmd_name == "tools":
                    return MockToolsCommand(name=cmd_name)
                return None

        monkeypatch.setattr(
            "q2lsp.qiime.q2cli_gateway._get_root_command",
            lambda: MockRootCommand(name="qiime"),
        )

        provider = create_qiime_help_provider(max_content_width=80, color=False)
        help_text = provider(["tools", "export"])

        assert help_text is not None
        # Verify proper command path formatting with full context chain
        assert "Usage: qiime tools export" in help_text
        assert "Export data" in help_text

    def test_provider_sanitizes_ansi_escape_sequences(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider removes ANSI escape sequences from help text."""

        class MockRootCommand(click.Command):
            name = "qiime"
            help_text = "QIIME 2 CLI"
            short_help = "QIIME 2"

            def get_help(self, ctx: click.Context) -> str:
                # Return help text with ANSI escape sequences
                return "\x1b[31mUsage:\x1b[0m qiime [OPTIONS]\n\n  QIIME 2 CLI.\n\nOptions:\n  --help  Show this message and exit.\n"

        monkeypatch.setattr(
            "q2lsp.qiime.q2cli_gateway._get_root_command",
            lambda: MockRootCommand(name="qiime"),
        )

        provider = create_qiime_help_provider(max_content_width=80, color=False)
        help_text = provider([])

        assert help_text is not None
        assert "Usage:" in help_text
        assert "\x1b[31m" not in help_text
        assert "\x1b[0m" not in help_text

    def test_provider_sanitizes_control_characters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider removes ASCII control characters except \\n and \\t."""

        class MockRootCommand(click.Command):
            name = "qiime"
            help_text = "QIIME 2 CLI"
            short_help = "QIIME 2"

            def get_help(self, ctx: click.Context) -> str:
                # Return help text with various control characters
                return "Usage:\b qiime [OPTIONS]\r\n\n  QIIME 2 CLI.\n\nOptions:\n  --help  Show this message and exit.\n\x00"

        monkeypatch.setattr(
            "q2lsp.qiime.q2cli_gateway._get_root_command",
            lambda: MockRootCommand(name="qiime"),
        )

        provider = create_qiime_help_provider(max_content_width=80, color=False)
        help_text = provider([])

        assert help_text is not None
        assert "Usage:" in help_text
        assert "\b" not in help_text
        assert "\r" not in help_text
        assert "\x00" not in help_text
        # Newlines should be preserved
        assert "\n" in help_text
        # CRLF should be normalized to LF
        assert "\r\n" not in help_text

    def test_provider_preserves_tabs_and_newlines(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider preserves tabs and newlines while sanitizing other control chars."""

        class MockRootCommand(click.Command):
            name = "qiime"
            help_text = "QIIME 2 CLI"
            short_help = "QIIME 2"

            def get_help(self, ctx: click.Context) -> str:
                # Return help text with tabs and newlines
                return "Usage:\n\tqiime [OPTIONS]\n\n  QIIME 2 CLI.\n\nOptions:\n\t--help  Show this message and exit.\n"

        monkeypatch.setattr(
            "q2lsp.qiime.q2cli_gateway._get_root_command",
            lambda: MockRootCommand(name="qiime"),
        )

        provider = create_qiime_help_provider(max_content_width=80, color=False)
        help_text = provider([])

        assert help_text is not None
        assert "Usage:" in help_text
        assert "\t" in help_text
        assert "\n" in help_text

    def test_provider_sanitizes_all_control_chars_excluding_whitespace(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider removes all control characters except \\n and \\t, including ANSI."""

        class MockRootCommand(click.Command):
            name = "qiime"
            help_text = "QIIME 2 CLI"
            short_help = "QIIME 2"

            def get_help(self, ctx: click.Context) -> str:
                # Return help text with mix of control characters and ANSI
                return "\x1b[31mUsage:\b\x1b[0m qiime [OPTIONS]\x07\r\n\n  QIIME 2 CLI.\n\x00Options:\n  --help  Show this message and exit.\n"

        monkeypatch.setattr(
            "q2lsp.qiime.q2cli_gateway._get_root_command",
            lambda: MockRootCommand(name="qiime"),
        )

        provider = create_qiime_help_provider(max_content_width=80, color=False)
        help_text = provider([])

        assert help_text is not None
        assert "Usage:" in help_text
        assert "QIIME 2 CLI" in help_text
        assert "Options:" in help_text
        assert "\x1b" not in help_text
        assert "\b" not in help_text
        assert "\x07" not in help_text
        assert "\r" not in help_text
        assert "\x00" not in help_text
        # Preserve newlines and tabs
        assert "\n" in help_text
