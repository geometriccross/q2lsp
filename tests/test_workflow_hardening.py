"""Policy tests for GitHub Actions workflow hardening."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _workflow_files() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[1]
    return sorted((repo_root / ".github" / "workflows").glob("*.yml"))


def _load_workflow(path: Path) -> dict[str, Any]:
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(content, dict):
        msg = f"Workflow must parse to mapping: {path}"
        raise AssertionError(msg)
    return content


def test_workflows_have_readonly_contents_permission() -> None:
    for workflow_path in _workflow_files():
        workflow = _load_workflow(workflow_path)
        permissions = workflow.get("permissions")
        assert isinstance(permissions, dict), (
            f"Missing top-level permissions in {workflow_path}"
        )
        assert permissions.get("contents") == "read", (
            f"permissions.contents must be read in {workflow_path}"
        )


def test_workflow_jobs_define_timeout_minutes() -> None:
    for workflow_path in _workflow_files():
        workflow = _load_workflow(workflow_path)
        jobs = workflow.get("jobs")
        assert isinstance(jobs, dict), f"Missing jobs in {workflow_path}"
        for job_name, job in jobs.items():
            assert isinstance(job, dict), (
                f"Job mapping required for {job_name} in {workflow_path}"
            )
            timeout = job.get("timeout-minutes")
            assert isinstance(timeout, int) and timeout > 0, (
                f"Job {job_name} in {workflow_path} must define positive timeout-minutes"
            )


def test_checkout_steps_disable_persisted_credentials() -> None:
    for workflow_path in _workflow_files():
        workflow = _load_workflow(workflow_path)
        jobs = workflow.get("jobs")
        assert isinstance(jobs, dict), f"Missing jobs in {workflow_path}"
        for job_name, job in jobs.items():
            assert isinstance(job, dict), (
                f"Job mapping required for {job_name} in {workflow_path}"
            )
            steps = job.get("steps")
            if not isinstance(steps, list):
                continue
            for step in steps:
                if not isinstance(step, dict):
                    continue
                uses = step.get("uses")
                if not isinstance(uses, str) or not uses.startswith(
                    "actions/checkout@"
                ):
                    continue
                with_section = step.get("with")
                assert isinstance(with_section, dict), (
                    f"actions/checkout step must define with.persist-credentials in {workflow_path} ({job_name})"
                )
                assert with_section.get("persist-credentials") is False, (
                    "actions/checkout must set persist-credentials: false "
                    f"in {workflow_path} ({job_name})"
                )
