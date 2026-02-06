"""Release workflow policy consistency checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _load_workflow(path: Path) -> dict[str, Any]:
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(content, dict):
        msg = f"Workflow must parse to mapping: {path}"
        raise AssertionError(msg)
    return content


def _on_section(workflow: dict[str, Any], workflow_path: Path) -> dict[str, Any]:
    on_section = workflow.get("on")
    if on_section is None:
        # PyYAML can resolve unquoted `on` as boolean True.
        raw_workflow: dict[Any, Any] = workflow
        on_section = raw_workflow.get(True)
    assert isinstance(on_section, dict), f"Missing on section in {workflow_path}"
    return on_section


def _job_steps(
    workflow: dict[str, Any], workflow_path: Path, job_name: str
) -> list[dict[str, Any]]:
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict), f"Missing jobs section in {workflow_path}"
    job = jobs.get(job_name)
    assert isinstance(job, dict), f"Missing {job_name} job in {workflow_path}"
    steps = job.get("steps")
    assert isinstance(steps, list), f"Missing steps for {job_name} in {workflow_path}"
    normalized_steps: list[dict[str, Any]] = []
    for step in steps:
        if isinstance(step, dict):
            normalized_steps.append(step)
    return normalized_steps


def test_python_release_workflow_has_tag_trigger_and_version_check() -> None:
    workflow_path = Path(".github/workflows/release-publish.yml")
    workflow = _load_workflow(workflow_path)

    on_section = _on_section(workflow, workflow_path)
    push = on_section.get("push")
    assert isinstance(push, dict), f"Missing push trigger in {workflow_path}"
    tags = push.get("tags")
    assert isinstance(tags, list), f"Missing push.tags in {workflow_path}"
    assert "q2lsp-v*" in tags, f"q2lsp-v* tag trigger required in {workflow_path}"

    steps = _job_steps(workflow, workflow_path, "build")
    assert any(
        step.get("name") == "Verify release tag matches project version"
        and "q2lsp-v" in str(step.get("run", ""))
        and "pyproject.toml" in str(step.get("run", ""))
        for step in steps
    ), f"Tag-version consistency step required in {workflow_path}"


def test_vscode_release_workflow_has_tag_trigger_and_version_check() -> None:
    workflow_path = Path(".github/workflows/vscode-extension-release.yml")
    workflow = _load_workflow(workflow_path)

    on_section = _on_section(workflow, workflow_path)
    push = on_section.get("push")
    assert isinstance(push, dict), f"Missing push trigger in {workflow_path}"
    tags = push.get("tags")
    assert isinstance(tags, list), f"Missing push.tags in {workflow_path}"
    assert "vscode-q2lsp-v*" in tags, (
        f"vscode-q2lsp-v* tag trigger required in {workflow_path}"
    )

    steps = _job_steps(workflow, workflow_path, "build-package")
    assert any(
        step.get("name") == "Verify release tag matches extension version"
        and "vscode-q2lsp-v" in str(step.get("run", ""))
        and "package.json" in str(step.get("run", ""))
        and "refs/tags/" in str(step.get("run", ""))
        for step in steps
    ), f"Tag-version consistency step required in {workflow_path}"
