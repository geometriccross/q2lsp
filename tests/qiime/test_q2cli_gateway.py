"""Tests for q2cli gateway module."""

from __future__ import annotations

from typing import cast

import click
import pytest
import q2lsp.qiime.q2cli_gateway as q2cli_gateway

from q2lsp.qiime.q2cli_gateway import (
    build_qiime_hierarchy,
    create_qiime_help_provider,
)
from q2lsp.qiime.types import JsonObject


class TestQ2CliGatewayPublicSurface:
    def test_legacy_root_taking_helpers_are_not_public(self) -> None:
        assert not hasattr(q2cli_gateway, "build_command_hierarchy")
        assert not hasattr(q2cli_gateway, "command_hierarchy_json")

    def test_unused_gateway_indirection_is_not_public(self) -> None:
        assert not hasattr(q2cli_gateway, "Q2CliGateway")
        assert not hasattr(q2cli_gateway, "build_qiime_hierarchy_via_gateway")
        assert not hasattr(q2cli_gateway, "qiime_hierarchy_json")

    def test_q2cli_implementation_types_are_not_public(self) -> None:
        assert not hasattr(q2cli_gateway, "RootCommand")
        assert not hasattr(q2cli_gateway, "PluginCommand")
        assert not hasattr(q2cli_gateway, "click")


class TestBuildQiimeHierarchy:
    def test_build_hierarchy_exposes_click_option_signature_metadata(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Public hierarchy preserves useful Click option signature details."""

        action = click.Command(
            "inspect",
            params=[
                click.Option(["--hidden-token"], hidden=True),
                click.Option(["--input-path"], required=True, help="Input path."),
                click.Option(["--threads"], default=4, help="Thread count."),
                click.Option(["--verbose/--no-verbose"], default=False),
            ],
        )

        class FakeBuiltin(click.MultiCommand):
            def list_commands(self, ctx: click.Context) -> list[str]:
                return ["inspect"]

            def get_command(
                self, ctx: click.Context, cmd_name: str
            ) -> click.Command | None:
                if cmd_name == "inspect":
                    return action
                return None

        class FakeRoot(click.MultiCommand):
            def __init__(self) -> None:
                super().__init__(name="qiime", help="Fake QIIME root")
                self._builtin_commands = {
                    "tools": FakeBuiltin(name="tools", help="Fake tools")
                }
                self._plugin_lookup = {}

        monkeypatch.setattr("q2lsp.qiime.q2cli_gateway._RootCommand", FakeRoot)

        hierarchy = build_qiime_hierarchy()

        root_entry = cast(JsonObject, hierarchy["qiime"])
        tools_entry = cast(JsonObject, root_entry["tools"])
        inspect_entry = cast(JsonObject, tools_entry["inspect"])
        signature = cast(list[JsonObject], inspect_entry["signature"])

        assert [param["name"] for param in signature] == [
            "input_path",
            "threads",
            "verbose",
        ]
        params_by_name = {param["name"]: param for param in signature}
        assert params_by_name["input_path"]["required"] is True
        assert "default" not in params_by_name["input_path"]
        assert params_by_name["threads"]["default"] == 4
        assert params_by_name["verbose"]["default"] is False
        assert params_by_name["verbose"]["is_bool_flag"] is True


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
