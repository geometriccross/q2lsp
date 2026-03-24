"""Import integrity tests for diagnostics submodules."""

from __future__ import annotations

import subprocess
import sys

import pytest


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
            "importlib.import_module('q2lsp.lsp.diagnostics.models')",
            f"importlib.import_module('{first_module}')",
            f"importlib.import_module('{second_module}')",
            "importlib.import_module('q2lsp.lsp.diagnostics.command_level')",
            "importlib.import_module('q2lsp.lsp.diagnostics.document_level')",
            "importlib.import_module('q2lsp.lsp.diagnostics.collector')",
            "importlib.import_module('q2lsp.lsp.diagnostics.hierarchy')",
            "importlib.import_module('q2lsp.lsp.diagnostics.matching')",
        ]
    )

    result = subprocess.run(
        [sys.executable, "-c", command],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_diagnostics_public_api_all_is_pinned() -> None:
    from q2lsp.lsp import diagnostics

    assert set(diagnostics.__all__) == {
        "DebounceManager",
        "DiagnosticIssue",
        "collect_diagnostics",
        "validate_command",
    }


def test_diagnostics_validate_command_backwards_compatible_import() -> None:
    from q2lsp.lsp.diagnostics import validate_command
    from q2lsp.lsp.diagnostics.validator import (
        validate_command as validate_command_impl,
    )
    from q2lsp.lsp.types import ParsedCommand, TokenSpan

    hierarchy = {
        "qiime": {
            "name": "qiime",
            "demo": {
                "name": "demo",
                "step": {
                    "name": "step",
                    "signature": [{"name": "table", "type": "input"}],
                },
            },
        }
    }
    command = ParsedCommand(
        tokens=[
            TokenSpan("qiime", 0, 5),
            TokenSpan("demo", 6, 10),
            TokenSpan("step", 11, 15),
        ],
        start=0,
        end=15,
    )

    assert validate_command(command, hierarchy) == validate_command_impl(
        command, hierarchy
    )
