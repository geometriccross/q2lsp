# Trusted Publishing Prerequisites

This document defines the required repository and account setup before implementing
the release publish workflow.

## 1) GitHub environments

Create these environments in repository settings:

- `testpypi`
- `pypi`

Configure both with protection rules:

1. Require at least one reviewer for deployments.
2. Restrict deployment branches/tags to protected refs used for release.
3. Keep environment secrets empty for publishing credentials (Trusted Publishing uses OIDC).

Recommended approval policy:

- `testpypi`: maintainers approve manually.
- `pypi`: stricter review than `testpypi` (for example two maintainers if team size allows).

## 2) PyPI/TestPyPI trusted publisher registration

Register a Trusted Publisher for both indexes:

- TestPyPI project settings -> Publishing
- PyPI project settings -> Publishing

For each registration, provide:

1. GitHub owner: `geometriccross`
2. Repository: `q2lsp`
3. Workflow filename: the release workflow file to be added in task `q2lsp-yh7`
4. Environment name: `testpypi` or `pypi` (must match GitHub job `environment` exactly)

Release jobs will require `permissions: { id-token: write, contents: read }` so the index can validate
GitHub OIDC identity.

## 3) Branch and tag protection expectations

Before enabling publishing, enforce:

1. Protected default branch (for example `main`) with required reviews and status checks.
2. Restrict who can push to release tags (for example `v*`).
3. Require pull request reviews for workflow and packaging metadata changes.

`CODEOWNERS` in this repository is used to require review from `@geometriccross` for release-related files.

## 4) What cannot be enforced in-repo

The following controls are external configuration and cannot be fully enforced by repository files alone:

- PyPI/TestPyPI project-side Trusted Publisher registration.
- GitHub environment reviewers and deployment branch/tag policies.
- Organization-level repository rulesets and branch/tag protection details.
- Human approval quality (repository policy can require approval, but not reviewer judgment quality).
