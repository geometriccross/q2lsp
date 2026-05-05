"""Release workflow policy consistency checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_workflow(path: Path) -> dict[str, Any]:
    assert path.exists(), f"Workflow file must exist: {path}"
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


def _assert_step_name_exists_once(
    steps: list[dict[str, Any]], workflow_path: Path, step_name: str
) -> dict[str, Any]:
    matching_steps = [step for step in steps if step.get("name") == step_name]
    assert len(matching_steps) == 1, (
        f"Expected exactly one {step_name!r} step in {workflow_path}, "
        f"found {len(matching_steps)}"
    )
    return matching_steps[0]


def test_python_release_workflow_has_tag_trigger_and_version_check() -> None:
    workflow_path = REPO_ROOT / ".github/workflows/release-publish.yml"
    workflow = _load_workflow(workflow_path)

    on_section = _on_section(workflow, workflow_path)
    push = on_section.get("push")
    assert isinstance(push, dict), f"Missing push trigger in {workflow_path}"
    tags = push.get("tags")
    assert isinstance(tags, list), f"Missing push.tags in {workflow_path}"
    assert "q2lsp-v*" in tags, f"q2lsp-v* tag trigger required in {workflow_path}"

    step = _assert_step_name_exists_once(
        _job_steps(workflow, workflow_path, "build"),
        workflow_path,
        "Verify release tag matches project version",
    )
    # This is a lightweight workflow structure check, not executable shell validation.
    run = str(step.get("run", ""))
    assert "q2lsp-v" in run, f"Project release tag prefix required in {workflow_path}"
    assert "pyproject.toml" in run, f"Project version source required in {workflow_path}"


def test_vscode_release_workflow_has_tag_trigger_and_version_check() -> None:
    workflow_path = REPO_ROOT / ".github/workflows/vscode-extension-release.yml"
    workflow = _load_workflow(workflow_path)

    on_section = _on_section(workflow, workflow_path)
    push = on_section.get("push")
    assert isinstance(push, dict), f"Missing push trigger in {workflow_path}"
    tags = push.get("tags")
    assert isinstance(tags, list), f"Missing push.tags in {workflow_path}"
    assert "vscode-q2lsp-v*" in tags, (
        f"vscode-q2lsp-v* tag trigger required in {workflow_path}"
    )

    step = _assert_step_name_exists_once(
        _job_steps(workflow, workflow_path, "build-package"),
        workflow_path,
        "Verify release tag matches extension version",
    )
    # This is a lightweight workflow structure check, not executable shell validation.
    run = str(step.get("run", ""))
    assert "vscode-q2lsp-v" in run, f"Extension release tag prefix required in {workflow_path}"
    assert "package.json" in run, f"Extension version source required in {workflow_path}"
    assert "refs/tags/" in run, f"Tag-only validation guard required in {workflow_path}"
