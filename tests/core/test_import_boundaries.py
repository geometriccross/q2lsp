"""Architecture boundary tests for q2lsp layered imports.

Rules enforced by these tests:
- core must not import from lsp, qiime, adapters, or usecases
- core must not import edge dependencies directly
- q2cli/click imports must stay inside explicit QIIME gateway modules
- qiime must not import from lsp, adapters, or usecases
- adapters must not import from lsp or usecases
- usecases must not import from lsp
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "q2lsp"
PROJECT_ROOT = SRC_ROOT.parent.parent
ALLOWED_Q2CLI_CLICK_IMPORT_PATHS = {"src/q2lsp/qiime/q2cli_gateway.py"}


def _is_forbidden_module(module: str, forbidden_prefixes: tuple[str, ...]) -> bool:
    return any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in forbidden_prefixes
    )


def _relative_display_path(file_path: Path) -> str:
    try:
        return file_path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return file_path.as_posix()


def _module_name_for_file(file_path: Path) -> str:
    try:
        relative_path = file_path.relative_to(SRC_ROOT.parent)
    except ValueError:
        package_root = file_path.parent
        while (package_root.parent / "__init__.py").exists():
            package_root = package_root.parent
        relative_path = file_path.relative_to(package_root.parent)

    module_parts = list(relative_path.with_suffix("").parts)
    if module_parts[-1] == "__init__":
        module_parts = module_parts[:-1]
    return ".".join(module_parts)


def _resolve_import_from_modules(file_path: Path, node: ast.ImportFrom) -> list[str]:
    if node.level == 0:
        return [] if node.module is None else [node.module]

    current_module = _module_name_for_file(file_path)
    current_package = (
        current_module
        if file_path.name == "__init__.py"
        else current_module.rpartition(".")[0]
    )
    relative_module = "." * node.level
    if node.module is not None:
        relative_module += node.module

    try:
        resolved_module = importlib.util.resolve_name(relative_module, current_package)
    except ImportError:
        return []

    if node.module is not None:
        return [resolved_module]

    return [f"{resolved_module}.{alias.name}" for alias in node.names]


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
        relative_path = _relative_display_path(file_path)

        for node in ast.walk(module_ast):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_forbidden_module(alias.name, forbidden_prefixes):
                        violations.append(
                            f"{relative_path}:{node.lineno} imports {alias.name}"
                        )

            if isinstance(node, ast.ImportFrom):
                for module in _resolve_import_from_modules(file_path, node):
                    if not _is_forbidden_module(module, forbidden_prefixes):
                        continue
                    violations.append(
                        f"{relative_path}:{node.lineno} imports {module}"
                    )

    return violations


def test_collect_forbidden_imports_resolves_relative_imports(tmp_path: Path) -> None:
    package_dir = tmp_path / "q2lsp"
    core_dir = package_dir / "core"
    lsp_dir = package_dir / "lsp"
    core_dir.mkdir(parents=True)
    lsp_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (core_dir / "__init__.py").write_text("", encoding="utf-8")
    (lsp_dir / "__init__.py").write_text("", encoding="utf-8")
    (core_dir / "sample.py").write_text(
        "from ..lsp.diagnostics import publish\n", encoding="utf-8"
    )

    violations = _collect_forbidden_imports(
        layer_dir=core_dir,
        forbidden_prefixes=("q2lsp.lsp",),
    )

    assert violations == [
        f"{(core_dir / 'sample.py').as_posix()}:1 imports q2lsp.lsp.diagnostics"
    ]


def test_collect_forbidden_imports_resolves_init_relative_imports(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "q2lsp"
    core_dir = package_dir / "core"
    lsp_dir = package_dir / "lsp"
    core_dir.mkdir(parents=True)
    lsp_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (core_dir / "__init__.py").write_text(
        "from ..lsp.diagnostics import publish\n", encoding="utf-8"
    )
    (lsp_dir / "__init__.py").write_text("", encoding="utf-8")

    violations = _collect_forbidden_imports(
        layer_dir=core_dir,
        forbidden_prefixes=("q2lsp.lsp",),
    )

    assert violations == [
        f"{(core_dir / '__init__.py').as_posix()}:1 imports q2lsp.lsp.diagnostics"
    ]


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


def test_core_must_not_import_edge_dependencies() -> None:
    violations = _collect_forbidden_imports(
        layer_dir=SRC_ROOT / "core",
        forbidden_prefixes=("pygls", "lsprotocol", "q2cli", "click"),
    )

    assert violations == [], (
        "Architecture violation: core must not depend on LSP or QIIME CLI edge "
        "dependencies.\n" + "\n".join(violations)
    )


def test_q2cli_and_click_imports_stay_in_qiime_gateway_modules() -> None:
    violations = _collect_forbidden_imports(
        layer_dir=SRC_ROOT,
        forbidden_prefixes=("q2cli", "click"),
    )
    unexpected_violations = [
        violation
        for violation in violations
        if violation.split(":", maxsplit=1)[0]
        not in ALLOWED_Q2CLI_CLICK_IMPORT_PATHS
    ]

    assert unexpected_violations == [], (
        "Architecture violation: q2cli/click imports must stay inside explicit allowed "
        "QIIME gateway paths.\n" + "\n".join(unexpected_violations)
    )


def test_removed_command_hierarchy_module_has_no_internal_callers() -> None:
    violations = _collect_forbidden_imports(
        layer_dir=SRC_ROOT,
        forbidden_prefixes=("q2lsp.qiime.command_hierarchy",),
    )
    unexpected_violations = [
        violation
        for violation in violations
        if violation.split(":", maxsplit=1)[0]
        != "src/q2lsp/qiime/command_hierarchy.py"
    ]

    assert unexpected_violations == [], (
        "Architecture violation: command_hierarchy was removed; "
        "internal code should use q2cli_gateway or owned interfaces.\n"
        + "\n".join(unexpected_violations)
    )


def test_removed_command_hierarchy_module_is_not_importable() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("q2lsp.qiime.command_hierarchy")


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
