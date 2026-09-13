---
status: accepted
---

# Collapse diagnostics validation into one deep module

The diagnostics pipeline was split across five shallow modules — `validator.py`, `stages.py`, `matching.py`, `command_level.py`, and `models.py` — with private functions leaking across module boundaries (e.g. `_has_help_invocation` imported by `command_level.py` from `stages.py`). We decided to collapse all five into a single module, `command_analysis.py`. Its public entry point is `analyze_command()`, which returns `CommandAnalysis` with issues and dependency references.

The initial implementation also exposed validation-only and dependency-only wrappers for tests. These had no production callers and have been removed. Validation helpers remain private. Validation and dependency extraction are now both tested through `analyze_command()`, without test-only production wrappers.

**Considered options**

- Keep the five-module split and make leaked private functions public.
- Keep the five-module split and duplicate `_has_help_invocation` in each consumer.
- Collapse into `command_analysis.py` with only `analyze_command()` public (current).
- Collapse into `command_analysis.py` with all three functions public (initial choice, subsequently simplified).

**Consequences**

Private validation stages, matching helpers, help-invocation detection, and dependency extraction stay internal to `command_analysis.py`. The return types `CommandAnalysis`, `CommandDependencies`, and `DependencyReference` live in the same module. The implementation now lives in `core/diagnostics/`. `lsp/features.py` calls `collect_diagnostics(doc, catalog)`, which combines command analysis and cross-command checks, then converts their issues into LSP diagnostics. `lsp/session.py` owns scheduling. Command analysis interprets option groups and help once; dependency extraction consumes valid groups rather than using diagnostic display spans as a validity signal. See [the current architecture](../architecture.md).
