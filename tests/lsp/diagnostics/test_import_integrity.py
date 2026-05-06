"""Import integrity tests for diagnostics submodules."""

from __future__ import annotations

import subprocess
import sys

import pytest


IMPORT_TIMEOUT_SECONDS = 10


@pytest.mark.parametrize(
    ("first_module", "second_module"),
    [
        (
            "q2lsp.lsp.diagnostics.validator",
            "q2lsp.lsp.diagnostics.stages",
        ),
        (
            "q2lsp.lsp.diagnostics.stages",
            "q2lsp.lsp.diagnostics.validator",
        ),
    ],
    ids=["validator_then_stages", "stages_then_validator"],
)
def test_diagnostics_submodules_cold_import_without_circular_dependencies(
    first_module: str, second_module: str
) -> None:
    command = "\n".join(
        [
            "import importlib",
            "importlib.import_module('q2lsp.lsp.diagnostics.diagnostic_issue')",
            "from q2lsp.lsp.diagnostics import "
            "DebounceManager, DiagnosticIssue, validate_command_with_catalog",
            f"importlib.import_module('{first_module}')",
            f"importlib.import_module('{second_module}')",
            "importlib.import_module('q2lsp.lsp.diagnostics.matching')",
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
        "validate_command_with_catalog",
    ]
