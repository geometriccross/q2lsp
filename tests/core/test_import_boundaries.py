"""Architecture boundary tests for q2lsp layered imports.

Rules enforced by these tests:
- core must not import from lsp, qiime, adapters, or usecases
- qiime must not import from lsp, adapters, or usecases
- adapters must not import from lsp or usecases
- usecases must not import from lsp
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "q2lsp"
PROJECT_ROOT = SRC_ROOT.parent.parent


def _is_forbidden_module(module: str, forbidden_prefixes: tuple[str, ...]) -> bool:
    return any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in forbidden_prefixes
    )


def _collect_forbidden_imports(
    layer_dir: Path,
    forbidden_prefixes: tuple[str, ...],
) -> list[str]:
    assert layer_dir.is_dir(), f"Layer directory does not exist: {layer_dir}"

    violations: list[str] = []

    for file_path in sorted(layer_dir.rglob("*.py")):
        module_ast = ast.parse(
            file_path.read_text(encoding="utf-8"), filename=str(file_path)
        )
        relative_path = file_path.relative_to(PROJECT_ROOT)

        for node in ast.walk(module_ast):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_forbidden_module(alias.name, forbidden_prefixes):
                        violations.append(
                            f"{relative_path}:{node.lineno} imports {alias.name}"
                        )

            if isinstance(node, ast.ImportFrom):
                if node.level != 0 or node.module is None:
                    continue

                if _is_forbidden_module(node.module, forbidden_prefixes):
                    violations.append(
                        f"{relative_path}:{node.lineno} imports {node.module}"
                    )

    return violations


def test_core_must_not_import_lsp_qiime_adapters_or_usecases() -> None:
    violations = _collect_forbidden_imports(
        layer_dir=SRC_ROOT / "core",
        forbidden_prefixes=(
            "q2lsp.lsp",
            "q2lsp.qiime",
            "q2lsp.adapters",
            "q2lsp.usecases",
        ),
    )

    assert violations == [], (
        "Architecture violation: core must not depend on lsp, qiime, adapters, or "
        "usecases.\n" + "\n".join(violations)
    )


def test_qiime_must_not_import_lsp_adapters_or_usecases() -> None:
    violations = _collect_forbidden_imports(
        layer_dir=SRC_ROOT / "qiime",
        forbidden_prefixes=(
            "q2lsp.lsp",
            "q2lsp.adapters",
            "q2lsp.usecases",
        ),
    )

    assert violations == [], (
        "Architecture violation: qiime must not depend on lsp, adapters, or usecases.\n"
        + "\n".join(violations)
    )


def test_adapters_must_not_import_lsp_or_usecases() -> None:
    violations = _collect_forbidden_imports(
        layer_dir=SRC_ROOT / "adapters",
        forbidden_prefixes=("q2lsp.lsp", "q2lsp.usecases"),
    )

    assert violations == [], (
        "Architecture violation: adapters must not depend on lsp or usecases.\n"
        + "\n".join(violations)
    )


def test_usecases_must_not_import_lsp() -> None:
    violations = _collect_forbidden_imports(
        layer_dir=SRC_ROOT / "usecases",
        forbidden_prefixes=("q2lsp.lsp",),
    )

    assert violations == [], (
        "Architecture violation: usecases must not depend on lsp.\n"
        + "\n".join(violations)
    )
