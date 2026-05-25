---
status: accepted
---

# Collapse diagnostics validation into one deep module

The diagnostics pipeline was split across five shallow modules — `validator.py`, `stages.py`, `matching.py`, `command_level.py`, and `models.py` — with private functions leaking across module boundaries (e.g. `_has_help_invocation` imported by `command_level.py` from `stages.py`). We decided to collapse all five into a single deep module, `command_analysis.py`, with three public functions:

- `analyze_command()` — primary entry point: returns `CommandAnalysis` with issues and dependency references.
- `validate_command_with_catalog()` — validation-only entry point for callers that need issue lists without dependency extraction.
- `extract_command_dependencies()` — dependency extraction entry point for callers that need references without validation.

The latter two exist because validation tests and dependency extraction tests are independently extensive; forcing them through `analyze_command()` would add noise (requiring `source_text` for pure validation tests, or catalog setup for pure dependency tests).

**Considered options**

- Keep the five-module split and make leaked private functions public.
- Keep the five-module split and duplicate `_has_help_invocation` in each consumer.
- Collapse into `command_analysis.py` with only `analyze_command()` public.
- Collapse into `command_analysis.py` with all three functions public (chosen).

**Consequences**

The diagnostics directory shrinks from 11 files to 6. Private validation stages, matching helpers, help-invocation detection, and dependency extraction all stay internal to `command_analysis.py`. The type definitions `CommandAnalysis`, `CommandDependencies`, and `DependencyReference` move into the same module since they are the return types of `analyze_command()`. `diagnostics_handler.py` switches from calling `validate_command_with_catalog()` directly to calling `analyze_command()` and reading `.issues` — this is a necessary follow-up change, not a semantic behavior change. Document-level diagnostics wiring (switching `diagnostics_handler.py` to use `collect_diagnostics`) is explicitly out of scope and tracked as a separate issue.
