"""Architecture guardrails for core package imports."""

from __future__ import annotations

import ast
from pathlib import Path


def test_core_package_does_not_import_qiime_or_lsp_layers() -> None:
    core_dir = Path(__file__).resolve().parents[2] / "src" / "q2lsp" / "core"
    violations: list[str] = []

    for file_path in sorted(core_dir.glob("*.py")):
        module_ast = ast.parse(file_path.read_text(encoding="utf-8"))
        for node in ast.walk(module_ast):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(("q2lsp.qiime", "q2lsp.lsp")):
                        violations.append(
                            f"{file_path.name}:{node.lineno}:{alias.name}"
                        )
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                if node.module.startswith(("q2lsp.qiime", "q2lsp.lsp")):
                    violations.append(f"{file_path.name}:{node.lineno}:{node.module}")

    assert violations == []
