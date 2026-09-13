---
status: accepted
---

# Use catalog facts instead of command hierarchy nodes

q2lsp completion and diagnostics should depend on QIIME command facts exposed by the QIIME command catalog, not on raw command hierarchy nodes. We decided that the catalog public interface will expose root, command, action, and option fact objects plus fact lookup methods; the command hierarchy will remain a private implementation detail and malformed hierarchy without a QIIME root command will be rejected at catalog construction.

**Considered Options**

- Keep raw accessors such as `root_node()`, `command_node()`, `action_node()`, and public `hierarchy` for compatibility.
- Keep string convenience accessors such as `command_names`, `valid_actions()`, and `is_builtin_leaf()` alongside fact objects.
- Expose only catalog facts and fact lookup methods.

**Consequences**

This makes the catalog seam deeper: q2cli discovery shape, option label derivation, requiredness, and help-text fallback stay local to the QIIME command catalog. `QiimeOptionFact` includes `value_type` for completion detail and `is_bool_flag` so diagnostics can preserve short help (`-h`) invocation behavior without traversing raw signature nodes. Editor features still own editor-facing results such as completion items, diagnostic issues, suggestions, ranges, and hover formatting. Completion reads only the catalog facts needed for the current context, without building a second command hierarchy. Hover uses the q2cli help provider to display full CLI help; the former catalog-only hover path has been removed. The cost is a larger interface migration: existing tests and callers that inspect command hierarchy nodes must be rewritten to assert catalog facts instead.
