# Releasing Runbook

This runbook describes how to operate the `release-publish` workflow.
Policy rules remain in `doc/prompts/RELEASE_POLICY.md`.

## 1) Prerequisites and setup checklist

Before pushing a release tag, confirm all of the following:

- GitHub workflow: `.github/workflows/release-publish.yml` exists on the release commit.
- GitHub environments exist: `testpypi` and `pypi`.
- Environment protections are configured (reviewers/approval gates as required).
- Trusted Publisher is registered on both indexes for this repo/workflow/environment pair:
  - TestPyPI project -> Publishing (`testpypi` environment)
  - PyPI project -> Publishing (`pypi` environment)
- `pyproject.toml` version is final and exactly matches the intended tag without `v`.
- Local quality/build checks pass:
  - `pixi run -e dev ruff check .`
  - `pixi run -e dev ruff format --check .`
  - `pixi run -e dev pyright`
  - `pixi run -e dev pytest`
  - `python -m build`
  - `twine check dist/*`

## 2) Stable release procedure (`vX.Y.Z`)

1. Update `pyproject.toml` to `X.Y.Z` and merge to the release branch.
2. Create and push the annotated tag:
   - `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
   - `git push origin vX.Y.Z`
3. Monitor GitHub Actions `release-publish` run.

Expected behavior:

- `build` runs validation + build, uploads one dist artifact bundle.
- `publish-testpypi` publishes that artifact bundle to TestPyPI (`testpypi` environment).
- `publish-pypi` waits for `build` + `publish-testpypi`, then publishes the same artifact bundle to PyPI (`pypi` environment) after environment approval.

## 3) Prerelease procedure (`vX.Y.ZaN`, `vX.Y.ZbN`, `vX.Y.ZrcN`)

1. Update `pyproject.toml` to the prerelease version (PEP 440 form).
2. Create and push the tag (for example `v1.2.0rc1`).
3. Monitor `release-publish`.

Expected routing:

- `build` runs and validates prerelease tag format.
- `publish-testpypi` runs.
- `publish-pypi` is skipped automatically (`if: needs.build.outputs.stable == 'true'`).

## 4) Post-publish verification

After the workflow completes:

1. Confirm workflow status is green and jobs match expected routing.
2. Confirm release appears on TestPyPI:
   - `https://test.pypi.org/project/q2lsp/`
3. For stable releases, confirm release appears on PyPI:
   - `https://pypi.org/project/q2lsp/`
4. Verify version, files, metadata, and release history pages.
5. Smoke-install:
   - TestPyPI prerelease/staging check:
     - `python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ q2lsp==X.Y.Z...`
   - PyPI stable check:
     - `python -m pip install q2lsp==X.Y.Z`

## 5) Failure handling playbooks

### A) TestPyPI publish failure

Symptoms: `publish-testpypi` fails; `publish-pypi` will not run.

1. Check failure cause in workflow logs (OIDC permissions, environment gate, index outage, package metadata).
2. Fix root cause on branch (do not retag old commit).
3. Re-run with a new version and new tag:
   - stable: bump patch (`X.Y.(Z+1)`)
   - prerelease: bump prerelease counter (`rcN+1`, `bN+1`, or `aN+1`)
4. Push the new tag and verify full run.

### B) PyPI publish or approval failure

Symptoms: `publish-testpypi` succeeds but `publish-pypi` is waiting for approval or fails.

1. If waiting: complete `pypi` environment approval in GitHub.
2. If failed after approval: inspect `publish-pypi` logs and PyPI project publishing settings.
3. Apply fix and issue a new patch release tag (`vX.Y.(Z+1)`).
4. Verify new run publishes to both indexes as expected for stable.

### C) Bad release rollback (already on PyPI)

Use yank + patch release; do not delete artifacts.

1. Yank the bad release on PyPI and record the yank reason.
2. Prepare fix and bump patch version (`X.Y.(Z+1)`).
3. Tag and publish the patch release via normal stable flow.
4. Announce remediation in release notes (impact + fixed version).

## 6) Hotfix process

Use this for urgent production issues in the latest stable line.

1. Branch from the current release base.
2. Implement minimal fix and run full local checks.
3. Bump patch version only.
4. Merge with required reviews.
5. Tag `vX.Y.(Z+1)` and publish via normal stable workflow.
6. Verify both indexes and publish short operator notes.

## 7) Audit and release-notes checklist

For each release, capture:

- Tag name, commit SHA, and date/time (UTC).
- Workflow run URL and final status.
- Artifact identity (version + file names).
- Environment approvals (`testpypi`/`pypi`) and approver(s).
- Publish destinations reached (TestPyPI only vs TestPyPI + PyPI).
- User-facing notes: changes, migration notes, known issues, rollback plan.
- Incident details (if any): failure mode, mitigation, follow-up actions.
