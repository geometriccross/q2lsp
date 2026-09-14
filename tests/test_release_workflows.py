"""Execute release metadata steps without building or publishing packages."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml


WORKFLOW_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def _run_release_metadata(
    workflow_name: str, job_name: str, directory: Path, ref: str
) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
    workflow: dict[str, Any] = yaml.safe_load(
        (WORKFLOW_DIR / workflow_name).read_text(encoding="utf-8")
    )
    # The output-producing step ID is a workflow interface, not a display name.
    step = next(
        step
        for step in workflow["jobs"][job_name]["steps"]
        if step.get("id") == "release-meta"
    )
    output_file = directory / "github-output"
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", step["run"]],
        cwd=directory,
        env={
            **os.environ,
            "GITHUB_REF": ref,
            "GITHUB_REF_NAME": ref.removeprefix("refs/tags/").removeprefix(
                "refs/heads/"
            ),
            "GITHUB_OUTPUT": str(output_file),
        },
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    outputs = (
        dict(
            line.split("=", 1)
            for line in output_file.read_text(encoding="utf-8").splitlines()
        )
        if output_file.exists()
        else {}
    )
    return result, outputs


@pytest.mark.parametrize(
    ("version", "prerelease", "stable"),
    [
        ("1.2.3", "false", "true"),
        ("1.2.3a1", "true", "false"),
        ("1.2.3b2", "true", "false"),
    ],
)
def test_python_release_metadata(
    tmp_path: Path, version: str, prerelease: str, stable: str
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nversion = "{version}"\n', encoding="utf-8"
    )
    result, outputs = _run_release_metadata(
        "release-publish.yml", "build", tmp_path, f"refs/tags/q2lsp-v{version}"
    )

    assert result.returncode == 0, result.stderr
    assert outputs == {"version": version, "prerelease": prerelease, "stable": stable}


@pytest.mark.parametrize(
    ("version", "tag"),
    [
        ("1.2.3", "q2lsp-v1.2.4"),
        ("1.2.3", "vscode-q2lsp-v1.2.3"),
        ("1.2.3", "q2lsp-v"),
        ("1.2.3rc1", "q2lsp-v1.2.3rc1"),
        ("1.2.3.dev1", "q2lsp-v1.2.3.dev1"),
    ],
)
def test_python_release_rejects_invalid_tags(
    tmp_path: Path, version: str, tag: str
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nversion = "{version}"\n', encoding="utf-8"
    )
    result, outputs = _run_release_metadata(
        "release-publish.yml", "build", tmp_path, f"refs/tags/{tag}"
    )

    assert result.returncode != 0
    assert outputs == {}


@pytest.mark.parametrize(
    "manifest", ['[project]\nname = "q2lsp"\n', '[other]\nversion = "1.2.3"\n']
)
def test_python_release_requires_project_version(tmp_path: Path, manifest: str) -> None:
    (tmp_path / "pyproject.toml").write_text(manifest, encoding="utf-8")
    result, outputs = _run_release_metadata(
        "release-publish.yml", "build", tmp_path, "refs/tags/q2lsp-v1.2.3"
    )

    assert result.returncode != 0
    assert outputs == {}


@pytest.mark.parametrize(
    ("version", "prerelease"),
    [
        ("1.2.3", "false"),
        ("1.2.3-beta.1", "true"),
        ("1.2.3a1", "true"),
        ("1.2.3b2", "true"),
        ("1.2.3rc1", "true"),
    ],
)
def test_extension_release_metadata(
    tmp_path: Path, version: str, prerelease: str
) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"version": version}), encoding="utf-8"
    )
    result, outputs = _run_release_metadata(
        "extension-release.yml",
        "build-package",
        tmp_path,
        f"refs/tags/vscode-q2lsp-v{version}",
    )

    assert result.returncode == 0, result.stderr
    assert outputs == {"prerelease": prerelease}


@pytest.mark.parametrize(
    "tag", ["vscode-q2lsp-v1.2.4", "q2lsp-v1.2.3", "vscode-q2lsp-v"]
)
def test_extension_release_rejects_invalid_tags(tmp_path: Path, tag: str) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"version": "1.2.3"}), encoding="utf-8"
    )
    result, outputs = _run_release_metadata(
        "extension-release.yml", "build-package", tmp_path, f"refs/tags/{tag}"
    )

    assert result.returncode != 0
    assert outputs == {}


def test_extension_branch_dry_run_does_not_require_a_release_tag(
    tmp_path: Path,
) -> None:
    result, outputs = _run_release_metadata(
        "extension-release.yml", "build-package", tmp_path, "refs/heads/main"
    )

    assert result.returncode == 0, result.stderr
    assert outputs == {"prerelease": "false"}
