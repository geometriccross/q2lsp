"""Import integrity tests for diagnostics submodules."""

from __future__ import annotations

import subprocess
import sys


IMPORT_TIMEOUT_SECONDS = 10


def test_diagnostics_submodules_cold_import_without_circular_dependencies() -> None:
    command = "\n".join(
        [
            "import importlib",
            "importlib.import_module('q2lsp.lsp.diagnostics.diagnostic_issue')",
            "from q2lsp.lsp.diagnostics import "
            "DebounceManager, DiagnosticIssue, analyze_command, collect_diagnostics",
            "importlib.import_module('q2lsp.lsp.diagnostics.command_analysis')",
            "importlib.import_module('q2lsp.lsp.diagnostics.collector')",
            "importlib.import_module('q2lsp.lsp.diagnostics.document_level')",
        ]
    )

    result = subprocess.run(
        [sys.executable, "-c", command],
        capture_output=True,
        check=False,
        text=True,
        timeout=IMPORT_TIMEOUT_SECONDS,
    )

    assert result.returncode == 0, result.stderr


def test_diagnostics_public_api_all_is_pinned() -> None:
    from q2lsp.lsp import diagnostics

    assert diagnostics.__all__ == [
        "DebounceManager",
        "DiagnosticIssue",
        "analyze_command",
        "collect_diagnostics",
    ]
