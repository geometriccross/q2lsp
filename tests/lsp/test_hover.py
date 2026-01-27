"""Tests for hover functionality."""

from __future__ import annotations

from typing import Callable

import pytest

from tests.helpers.cursor import extract_cursor_offset

from q2lsp.lsp.hover import get_hover_help
from q2lsp.qiime.types import CommandHierarchy


@pytest.fixture
def hover_hierarchy() -> CommandHierarchy:
    """Minimal hierarchy for hover testing."""
    return {
        "qiime": {
            "name": "qiime",
            "help": "QIIME 2 command-line interface\n\nUsage: qiime [OPTIONS] COMMAND [ARGS]...",
            "short_help": "QIIME 2 CLI",
            "builtins": ["info"],
            "info": {
                "name": "info",
                "help": "Display information about current deployment",
                "short_help": "Display deployment info",
                "type": "builtin",
            },
            "feature-table": {
                "id": "feature-table",
                "name": "feature-table",
                "short_description": "Plugin for working with feature tables",
                "description": "Full description of feature-table plugin",
                "summarize": {
                    "id": "summarize",
                    "name": "summarize",
                    "description": "Summarize a feature table",
                    "epilog": [
                        "Example: qiime feature-table summarize --i-table table.qza",
                    ],
                },
            },
        }
    }


class TestGetHoverHelp:
    """Tests for get_hover_help function."""

    def test_hover_on_qiime_root(self, hover_hierarchy: CommandHierarchy) -> None:
        """Hover on 'qiime' token shows root help."""
        text, offset = extract_cursor_offset(text_with_cursor="qii<CURSOR>me info")
        help_text = get_hover_help(text, offset, hierarchy=hover_hierarchy)
        assert help_text is not None
        assert "QIIME 2 command-line interface" in help_text

    def test_hover_on_plugin(self, hover_hierarchy: CommandHierarchy) -> None:
        """Hover on plugin token shows plugin help."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime fe<CURSOR>ature-table summarize"
        )
        help_text = get_hover_help(text, offset, hierarchy=hover_hierarchy)
        assert help_text is not None
        assert (
            "feature-table" in help_text
            or "Plugin for working with feature tables" in help_text
        )

    def test_hover_on_action(self, hover_hierarchy: CommandHierarchy) -> None:
        """Hover on action token shows action help."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime feature-table sum<CURSOR>marize"
        )
        help_text = get_hover_help(text, offset, hierarchy=hover_hierarchy)
        assert help_text is not None
        assert "Summarize a feature table" in help_text

    def test_hover_with_epilog(self, hover_hierarchy: CommandHierarchy) -> None:
        """Hover on action includes epilog if present."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime feature-table summarize<CURSOR>"
        )
        help_text = get_hover_help(text, offset, hierarchy=hover_hierarchy)
        assert help_text is not None
        # epilog lines should be appended
        assert "Example:" in help_text or "qiime feature-table summarize" in help_text

    def test_hover_on_whitespace_returns_none(
        self, hover_hierarchy: CommandHierarchy
    ) -> None:
        """Hover on whitespace returns None."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime  <CURSOR> info")
        help_text = get_hover_help(text, offset, hierarchy=hover_hierarchy)
        assert help_text is None

    def test_hover_on_non_qiime_command_returns_none(
        self, hover_hierarchy: CommandHierarchy
    ) -> None:
        """Hover on non-qiime command returns None."""
        text, offset = extract_cursor_offset(text_with_cursor="echo <CURSOR>hello")
        help_text = get_hover_help(text, offset, hierarchy=hover_hierarchy)
        assert help_text is None

    def test_hover_on_builtin_plugin(self, hover_hierarchy: CommandHierarchy) -> None:
        """Hover on builtin command shows builtin help."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime in<CURSOR>fo")
        help_text = get_hover_help(text, offset, hierarchy=hover_hierarchy)
        assert help_text is not None
        assert "info" in help_text.lower()

    def test_hover_with_line_continuation(
        self, hover_hierarchy: CommandHierarchy
    ) -> None:
        """Hover works correctly with line continuations."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime \\\nfe<CURSOR>ature-table summarize"
        )
        help_text = get_hover_help(text, offset, hierarchy=hover_hierarchy)
        assert help_text is not None

    def test_hover_root_short_help_fallback(
        self, hover_hierarchy: CommandHierarchy
    ) -> None:
        """Root hover uses short_help if help is None."""
        hierarchy = {
            "qiime": {
                "name": "qiime",
                "help": None,
                "short_help": "QIIME 2 CLI",
                "builtins": [],
            }
        }
        text, offset = extract_cursor_offset(text_with_cursor="qii<CURSOR>me")
        help_text = get_hover_help(text, offset, hierarchy=hierarchy)
        assert help_text is not None
        assert "QIIME 2 CLI" in help_text

    def test_hover_plugin_description_fallback(
        self, hover_hierarchy: CommandHierarchy
    ) -> None:
        """Plugin hover uses description if short_description is None."""
        hierarchy = {
            "qiime": {
                "name": "qiime",
                "help": "Root help",
                "short_help": "Root short",
                "builtins": [],
                "test-plugin": {
                    "id": "test-plugin",
                    "name": "test-plugin",
                    "short_description": None,
                    "description": "Full plugin description",
                },
            }
        }
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime test-<CURSOR>plugin"
        )
        help_text = get_hover_help(text, offset, hierarchy=hierarchy)
        assert help_text is not None
        assert "Full plugin description" in help_text

    def test_hover_on_parameter_returns_none(
        self, hover_hierarchy: CommandHierarchy
    ) -> None:
        """Hover on parameter token returns None (not implemented)."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime feature-table summarize --<CURSOR>help"
        )
        help_text = get_hover_help(text, offset, hierarchy=hover_hierarchy)
        assert help_text is None

    def test_hover_after_command_returns_none(
        self, hover_hierarchy: CommandHierarchy
    ) -> None:
        """Hover after the command returns None."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime feature-table summarize --help <CURSOR>"
        )
        help_text = get_hover_help(text, offset, hierarchy=hover_hierarchy)
        assert help_text is None


class TestGetHoverHelpWithProvider:
    """Tests for get_hover_help function with help provider callback."""

    @pytest.fixture
    def sample_full_help(self) -> str:
        """Sample full help text matching click/q2cli format."""
        return """Usage: qiime [OPTIONS] COMMAND [ARGS]...

  QIIME 2 command-line interface.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  info       Display information about current deployment
  tools      QIIME 2 tools
"""

    @pytest.fixture
    def stub_help_provider(
        self, sample_full_help: str
    ) -> Callable[[list[str]], str | None]:
        """Create a stub help provider for testing."""

        def _get_help(command_path: list[str]) -> str | None:
            if not command_path:
                return sample_full_help
            elif command_path == ["info"]:
                return """Usage: qiime info [OPTIONS]

  Display information about current deployment.

Options:
  --help  Show this message and exit.
"""
            elif command_path == ["feature-table"]:
                return """Usage: qiime feature-table [OPTIONS] COMMAND [ARGS]...

  Plugin for working with feature tables.

Options:
  --help  Show this message and exit.

Commands:
  summarize  Summarize a feature table
"""
            elif command_path == ["feature-table", "summarize"]:
                return """Usage: qiime feature-table summarize [OPTIONS]

  Summarize a feature table.

Options:
  --help  Show this message and exit.
"""
            return None

        return _get_help

    def test_hover_on_qiime_root_returns_full_help(
        self, stub_help_provider: Callable[[list[str]], str | None]
    ) -> None:
        """Hover on 'qiime' token shows full CLI help text."""
        text, offset = extract_cursor_offset(text_with_cursor="qii<CURSOR>me info")
        help_text = get_hover_help(text, offset, get_help=stub_help_provider)
        assert help_text is not None
        assert "Usage:" in help_text
        assert "Options:" in help_text
        assert "Commands:" in help_text
        assert "QIIME 2 command-line interface" in help_text

    def test_hover_on_plugin_returns_full_help(
        self, stub_help_provider: Callable[[list[str]], str | None]
    ) -> None:
        """Hover on plugin token shows full CLI help text for plugin."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime fe<CURSOR>ature-table summarize"
        )
        help_text = get_hover_help(text, offset, get_help=stub_help_provider)
        assert help_text is not None
        assert "Usage:" in help_text
        assert "qiime feature-table" in help_text
        assert "Plugin for working with feature tables" in help_text

    def test_hover_on_action_returns_full_help(
        self, stub_help_provider: Callable[[list[str]], str | None]
    ) -> None:
        """Hover on action token shows full CLI help text for action."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime feature-table sum<CURSOR>marize"
        )
        help_text = get_hover_help(text, offset, get_help=stub_help_provider)
        assert help_text is not None
        assert "Usage:" in help_text
        assert "qiime feature-table summarize" in help_text
        assert "Summarize a feature table" in help_text

    def test_hover_on_builtin_returns_full_help(
        self, stub_help_provider: Callable[[list[str]], str | None]
    ) -> None:
        """Hover on builtin token shows full CLI help text."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime in<CURSOR>fo")
        help_text = get_hover_help(text, offset, get_help=stub_help_provider)
        assert help_text is not None
        assert "Usage:" in help_text
        assert "qiime info" in help_text
        assert "Display information about current deployment" in help_text

    def test_hover_provider_returns_none(
        self, stub_help_provider: Callable[[list[str]], str | None]
    ) -> None:
        """Hover returns None when provider returns None."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime unknown-<CURSOR>plugin"
        )

        def failing_provider(command_path: list[str]) -> str | None:
            return None

        help_text = get_hover_help(text, offset, get_help=failing_provider)
        assert help_text is None

    def test_hover_with_line_continuation_uses_provider(
        self, stub_help_provider: Callable[[list[str]], str | None]
    ) -> None:
        """Hover works correctly with line continuations."""
        text, offset = extract_cursor_offset(
            text_with_cursor="qiime \\\nfe<CURSOR>ature-table summarize"
        )
        help_text = get_hover_help(text, offset, get_help=stub_help_provider)
        assert help_text is not None
        assert "qiime feature-table" in help_text

    def test_hover_on_whitespace_returns_none_with_provider(
        self, stub_help_provider: Callable[[list[str]], str | None]
    ) -> None:
        """Hover on whitespace returns None."""
        text, offset = extract_cursor_offset(text_with_cursor="qiime  <CURSOR> info")
        help_text = get_hover_help(text, offset, get_help=stub_help_provider)
        assert help_text is None

    def test_hover_on_non_qiime_command_returns_none_with_provider(
        self, stub_help_provider: Callable[[list[str]], str | None]
    ) -> None:
        """Hover on non-qiime command returns None."""
        text, offset = extract_cursor_offset(text_with_cursor="echo <CURSOR>hello")
        help_text = get_hover_help(text, offset, get_help=stub_help_provider)
        assert help_text is None
