"""Integration tests for parsing and validating QIIME diagnostics.

These tests verify that parsed QIIME commands produce validation issues
for typos without exercising LSP diagnostic publishing.
"""

from __future__ import annotations

import pytest

from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.types import CommandHierarchy


class TestDiagnosticsParserValidatorIntegration:
    """Integration tests for QIIME command parsing and validation."""

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
                                "type": "input",
                            },
                            {
                                "name": "obs_metadata",
                                "type": "parameter",
                                "default": None,
                            },
                        ],
                    },
                },
            }
        }

    def test_typo_produces_validation_issue(
        self, mock_hierarchy: CommandHierarchy
    ) -> None:
        """Test that a typo in a plugin name produces a validation issue."""

        # Create mock document with typo
        class MockDocument:
            uri = "file:///test.sh"
            version = 1
            source = "qiime feature-tabel summarize"

        from q2lsp.lsp.diagnostics import validate_command_with_catalog
        from q2lsp.lsp.parser import find_qiime_commands, merge_line_continuations

        doc = analyze_document(MockDocument.source)

        issues = validate_command_with_catalog(
            commands[0], QiimeCatalog.from_hierarchy(mock_hierarchy)
        )

        assert len(issues) == 1
        assert "feature-tabel" in issues[0].message
        assert "Did you mean" in issues[0].message
        assert issues[0].start == 6
        assert issues[0].end == 19

    def test_valid_command_no_issues(self, mock_hierarchy: CommandHierarchy) -> None:
        """Test that a valid command produces no validation issues."""
        from q2lsp.lsp.diagnostics import validate_command_with_catalog
        from q2lsp.lsp.parser import find_qiime_commands, merge_line_continuations

        class MockDocument:
            source = "qiime feature-table summarize --i-table table.qza"

        doc = analyze_document(MockDocument.source)

        issues = validate_command_with_catalog(
            commands[0], QiimeCatalog.from_hierarchy(mock_hierarchy)
        )

        assert issues == []

    def test_option_typo_validation_issue(
        self, mock_hierarchy: CommandHierarchy
    ) -> None:
        """Test that an option typo produces a validation issue with correct code."""
        from q2lsp.lsp.diagnostics import validate_command_with_catalog
        from q2lsp.lsp.parser import find_qiime_commands, merge_line_continuations

        class MockDocument:
            source = "qiime feature-table summarize --i-tabel"

        doc = analyze_document(MockDocument.source)

        issues = validate_command_with_catalog(
            commands[0], QiimeCatalog.from_hierarchy(mock_hierarchy)
        )

        assert len(issues) == 1
        assert "--i-tabel" in issues[0].message
        assert "Did you mean" in issues[0].message
        assert "'--i-table'" in issues[0].message
        assert issues[0].code == "q2lsp-dni/unknown-option"
        assert issues[0].start == 30  # position of --i-tabel
        assert issues[0].end == 39
