"""Run the analyzer with transport and discovery dependencies unavailable."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_core_runs_without_lsp_or_q2cli() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import importlib
import pkgutil
import sys

for name in ("pygls", "lsprotocol", "q2cli", "click", "q2lsp.lsp"):
    sys.modules[name] = None

import q2lsp.core
for module in pkgutil.walk_packages(q2lsp.core.__path__, "q2lsp.core."):
    importlib.import_module(module.name)

from q2lsp.core.document import analyze_document
from q2lsp.core.completion import get_completions
from q2lsp.core.diagnostics import collect_diagnostics, codes
from q2lsp.qiime.catalog import QiimeCatalog

catalog = QiimeCatalog.from_hierarchy({"qiime": {"demo": {}}})
document = analyze_document("qiime de")
assert [item.label for item in get_completions(document.cursor_at(8), catalog)] == ["demo"]
assert [issue.code for issue in collect_diagnostics(document, catalog)] == [codes.UNKNOWN_ROOT]
""",
        ],
        env={**os.environ, "PYTHONPATH": str(source_root)},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
