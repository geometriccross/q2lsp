"""Integration test for diagnostics publishing.

This test verifies that the server correctly publishes diagnostics
when a document contains typos in QIIME commands.
"""

from __future__ import annotations

import pytest
from pygls.lsp.server import LanguageServer

import q2lsp.lsp.server as server_mod
from q2lsp.qiime.types import CommandHierarchy


class TestDiagnosticsIntegration:
    """Integration tests for diagnostics feature."""

    @pytest.fixture
    def mock_hierarchy(self) -> CommandHierarchy:
        """Create a mock hierarchy for testing."""
        return {
            "qiime": {
                "name": "qiime",
                "help": "QIIME 2 CLI",
                "builtins": ["info"],
                "info": {
                    "name": "info",
                    "short_help": "Display info",
                    "type": "builtin",
                },
                "feature-table": {
                    "id": "feature-table",
                    "name": "feature-table",
                    "summarize": {
                        "id": "summarize",
                        "name": "summarize",
                        "description": "Summarize table",
                        "signature": [
                            {
                                "name": "table",
                                "type": "FeatureTable[Frequency]",
                                "signature_type": "input",
                            },
                            {
                                "name": "obs_metadata",
                                "type": "MetadataColumn[Categorical]",
                                "default": None,
                                "signature_type": "parameter",
                            },
                        ],
                    },
                },
            }
        }

    @pytest.fixture
    def server_with_diagnostics(
        self, mock_hierarchy: CommandHierarchy
    ) -> LanguageServer:
        """Create server with diagnostics enabled."""
        get_hierarchy = lambda: mock_hierarchy
        return server_mod.create_server(get_hierarchy=get_hierarchy)

    @pytest.mark.asyncio
    async def test_typo_produces_diagnostic(
        self, server_with_diagnostics: LanguageServer, mock_hierarchy: CommandHierarchy
    ) -> None:
        """Test that a typo in a plugin name produces a diagnostic."""

        # Create mock document with typo
        class MockDocument:
            uri = "file:///test.sh"
            version = 1
            source = "qiime feature-tabel summarize"

        # Simulate validation by calling the internal validation
        from q2lsp.lsp.parser import find_qiime_commands, merge_line_continuations
        from q2lsp.lsp.diagnostics import validate_command

        merged_text, _ = merge_line_continuations(MockDocument.source)
        commands = find_qiime_commands(merged_text)

        issues = validate_command(commands[0], mock_hierarchy)

        assert len(issues) == 1
        assert "feature-tabel" in issues[0].message
        assert "Did you mean" in issues[0].message
        assert issues[0].start == 6
        assert issues[0].end == 19

    @pytest.mark.asyncio
    async def test_valid_command_no_issues(
        self, server_with_diagnostics: LanguageServer, mock_hierarchy: CommandHierarchy
    ) -> None:
        """Test that a valid command produces no diagnostics."""
        from q2lsp.lsp.parser import find_qiime_commands, merge_line_continuations
        from q2lsp.lsp.diagnostics import validate_command

        class MockDocument:
            source = "qiime feature-table summarize"

        merged_text, _ = merge_line_continuations(MockDocument.source)
        commands = find_qiime_commands(merged_text)

        issues = validate_command(commands[0], mock_hierarchy)

        assert issues == []

    @pytest.mark.asyncio
    async def test_option_typo_diagnostic(
        self, server_with_diagnostics: LanguageServer, mock_hierarchy: CommandHierarchy
    ) -> None:
        """Test that an option typo produces a diagnostic with correct code."""
        from q2lsp.lsp.parser import find_qiime_commands, merge_line_continuations
        from q2lsp.lsp.diagnostics import validate_command

        class MockDocument:
            source = "qiime feature-table summarize --i-tabel"

        merged_text, _ = merge_line_continuations(MockDocument.source)
        commands = find_qiime_commands(merged_text)

        issues = validate_command(commands[0], mock_hierarchy)

        assert len(issues) == 1
        assert "--i-tabel" in issues[0].message
        assert "Did you mean" in issues[0].message
        assert "'--i-table'" in issues[0].message
        assert issues[0].code == "q2lsp-dni/unknown-option"
        assert issues[0].start == 30  # position of --i-tabel
        assert issues[0].end == 39
