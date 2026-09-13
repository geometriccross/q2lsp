# Setup Wizard Redesign Plan

Status: design export, not yet implemented.

## Goal

Redesign the VS Code Setup Wizard so users can either connect an existing QIIME 2 environment or create a new QIIME 2 environment, then configure q2lsp to use the selected Python interpreter.

The Wizard should be validation-driven: sending commands to a terminal never counts as success. Only explicit validation success advances setup state.

## Entry routes

The first screen branches into two clear routes:

1. **Use existing QIIME 2 environment**
2. **Create new QIIME 2 environment**

Use a route-aware guided checklist instead of independent page steppers. Each route shows checklist items with status values such as not started, current, running, passed, failed, or skipped, while emphasizing one current next action.

## Relationship with Environment Diagnosis

Environment Diagnosis is a lightweight readiness check for the QIIME 2 environment q2lsp would use. It should show short success/failure notifications and route failures to the Setup Wizard for guided repair or creation.

The Setup Wizard handles:

- existing-environment connection and repair
- new-environment creation guidance
- q2lsp installation guidance
- saving `q2lsp.interpreterPath`

## Existing environment route

### Interpreter candidates

The Wizard should show detected interpreter candidates before asking users to browse the filesystem.

Display order:

1. configured `q2lsp.interpreterPath`
2. active VS Code Python interpreter
3. `python3` from PATH
4. `python` from PATH
5. manual file picker selection, added after the user chooses one

Runtime resolver behavior can remain stricter, but the Wizard should show repair alternatives even when `q2lsp.interpreterPath` is configured.

### Candidate validation

Validate candidate interpreters asynchronously when the list is shown. Status should be two-stage:

- `QIIME 2: Ready | Missing`
- `q2lsp: Ready | Missing`

If the executable cannot run, show it as unavailable.

Do not require users to infer environment quality from paths alone.

### Manual interpreter selection

Manual file picker selection is not a separate one-off path. The chosen executable is added to the candidate list as a temporary `Manual selection` candidate and follows the same validation/status flow.

### Candidate behavior

If selected candidate is:

- **QIIME 2 Ready / q2lsp Ready**: show summary and proceed to saving interpreter path.
- **QIIME 2 Ready / q2lsp Missing**: show summary with primary action `Install q2lsp in Terminal`; after terminal command finishes, user clicks `Validate q2lsp`.
- **QIIME 2 Missing**: selectable, but blocked from proceeding. Show recovery actions: choose another interpreter, create a new QIIME 2 environment, show log.

### Existing route checklist

1. Select Python interpreter
2. Validate QIIME 2
3. Install or validate q2lsp
4. Save interpreter path
5. Setup complete

Saving `q2lsp.interpreterPath` is the completion condition. Restart should be handled automatically or by existing configuration-change behavior. `Restart now` may be optional secondary support, not a required step.

Save scope:

- Workspace should be the primary/default save target.
- User scope is secondary/advanced.

## New environment route

### Manager selection

Manager choices:

- Conda / Miniconda: recommended default
- Pixi: advanced
- Manual: custom escape hatch

If selected manager is missing, environment creation is blocked until manager validation passes.

Manager missing UI should guide recovery:

```text
Conda was not found.

Install Miniconda, then check again.

[ Install Miniconda in Terminal ]
[ I installed it — check again ]
```

Manual route is exempt from manager checks.

### Terminal-centered execution

Long-running setup work should run in the user’s terminal. The Wizard presents commands and validates results; it should not treat terminal command dispatch as success.

Primary action labels should be specific:

- `Install Miniconda in Terminal`
- `Create environment in Terminal`
- `Install q2lsp in Terminal`

After sending a command to the terminal, do not auto-advance. The user validates after the terminal command finishes.

### QIIME 2 environment target

The new-environment route uses a **QIIME 2 environment target**: the selected version, distribution, platform, and environment file used to create the environment.

Main UI shows:

- Version
- Distribution

Advanced details shows the resolved environment file URL as read-only for now.

Do not allow platform/environment-file override in this redesign. The current implementation can fetch remote files for multiple platforms, but selected-file platform handling is not complete enough to expose safely.

### Metadata loading

If QIIME 2 environment metadata cannot be loaded, block new-environment creation and show retry/recovery actions.

Recommended UI:

```text
Could not load QIIME 2 environment metadata.

The Setup Wizard needs the official QIIME 2 environment list before it can create a command.

[ Retry ] [ Open QIIME 2 Quickstart ]
```

Do not silently fall back to synthetic metadata for the main UX.

### Target fixation after terminal command

After `Create environment in Terminal`, store the submitted environment target in temporary WebView state. This is not persisted to disk.

Purpose: prevent validation from drifting if the user changes version/distribution selectors while the terminal command is still running.

Post-submission UI should show:

```text
Command sent to Terminal for:
QIIME 2 <version> <distribution>
Environment: <name>

[ Validate QIIME 2 ] [ Change target ]
```

Hide or disable selectors until `Change target` returns to the unsubmitted state.

Do not persist in-progress target state unless future requirements include restoring wizard progress after WebView close or VS Code restart.

### New route checklist

1. Choose manager
2. Validate manager
3. Choose QIIME 2 target
4. Create environment in Terminal
5. Validate QIIME 2
6. Install or validate q2lsp
7. Save interpreter path
8. Setup complete

## q2lsp installation

Install latest q2lsp instead of pinning to the VS Code extension version:

```bash
python -m pip install -U q2lsp
```

Rationale:

- q2lsp server is launched through standard LSP over stdio.
- The extension and Python server do not currently require exact version matching.
- Latest server gets bug fixes.
- If protocol-breaking changes are introduced later, add explicit compatibility checks then.

Validation should display installed q2lsp version as information only. Do not warn on version mismatch.

Example:

```text
✓ q2lsp validated
Server package: q2lsp 4.1.0
Python: /opt/qiime2/bin/python
```

## Accessibility and UI requirements

High-priority improvements:

- Track pending command/action state.
- Disable the active action while pending.
- Use `role="status"` and `aria-live="polite"` for progress/status updates.
- Use `role="alert"` for errors.
- Add explicit `:focus-visible` styles for cards, buttons, and selects:
  - `outline: 2px solid var(--vscode-focusBorder)`
  - `outline-offset: 2px`
- Make progress/checklist state meaningful to assistive technology.
- Avoid empty command previews while metadata is loading or missing.

Responsive behavior:

- Default narrow layout should be single-column.
- Restore multi-column layout only at wider breakpoints.
- Avoid fixed-width layouts that break in narrow VS Code webviews or side panels.

Visual behavior:

- Use VS Code theme variables.
- Add subtle hover/focus transitions.
- Make the next primary action visually dominant.
- Keep secondary/recovery actions visible but subordinate.

## Copy decisions

Prefer direct, specific wording:

- `Check installation`
- `I installed it — check again`
- `Install Miniconda in Terminal`
- `Create environment in Terminal`
- `Install q2lsp in Terminal`
- `Validate QIIME 2`
- `Validate q2lsp`

Avoid ambiguous wording like `skip it` unless it is a true skip action.

## Implementation outline

1. Replace page-step state with route-aware checklist state.
2. Add existing-environment route selection and interpreter candidate list.
3. Add candidate discovery using existing interpreter resolver helpers where possible.
4. Add per-candidate async validation with QIIME 2/q2lsp split status.
5. Add manual interpreter file picker and candidate insertion.
6. Change heavy actions to terminal-centered command dispatch.
7. Add manager-required gating for new-environment creation.
8. Add metadata loading/error states and retry/Quickstart actions.
9. Make environment file URL advanced read-only.
10. Store submitted environment target temporarily after terminal command dispatch.
11. Add q2lsp version extraction/display during validation.
12. Add accessibility, pending, focus-visible, and responsive CSS updates.
13. Update setup wizard tests for route selection, candidates, metadata failure, manager gating, target fixation, and q2lsp version display.
