# LSP architecture

## Data flow

```text
pygls workspace (authoritative source + version)
  -> DocumentSession (one cached analysis per URI/version/source)
    -> core.document.analyze_document(source)
      -> continuation mapping + shell tokens/commands + source line index
    -> immutable Document
      -> completion / hover / CodeLens / diagnostics
        -> lsp.adapter (original-source ranges -> UTF-16 positions)
          -> LSP response

q2cli -> qiime catalog provider -> completion and diagnostics
q2cli -> CLI help provider     -> hover
```

Analysis is syntax-only. It does not load a catalog, request help, execute QIIME,
or retain a mutable pygls document. Requests and debounced diagnostics share the
same `Document`. CodeLens uses the original source slice, not reconstructed tokens,
so shell quoting and variable expansion survive in `q2lsp.runCommand` arguments.

## Responsibilities

| Module | Owns |
| --- | --- |
| `core/shell.py` | Shell word decoding, command segmentation, QIIME command detection; immutable token/command spans |
| `core/document.py` | Source snapshot, continuation source map, line index, feature-neutral cursor facts |
| `core/completion.py` | Candidate selection, prefix matching, used-option filtering |
| `core/diagnostics/command_analysis.py` | Name/option checks, requiredness, help suppression, valid input/output references |
| `core/diagnostics/document_level.py` | Dependency cycles and duplicate output paths |
| `qiime/` | Catalog facts, option grouping, signature conventions, q2cli discovery and help |
| `lsp/features.py` | LSP feature inputs/outputs, lazy provider calls, diagnostic severity and hover formatting |
| `lsp/adapter.py` | LSP coordinate/result conversion and completion edits |
| `lsp/session.py` | Derived-document cache, diagnostic debounce/cancellation, close/shutdown cleanup |
| `lsp/server.py` | Dependency composition, request registration, feature failure defaults |
| `lsp/protocol.py` | Existing pygls UTF-16 initialization compatibility override |

`core` may use QIIME catalog facts and pure option helpers, but must not import
`lsp`, pygls, lsprotocol, q2cli, or click. `qiime` must not depend on `core` or
`lsp`. Only the outer LSP layer knows about both transport and analysis.

There is no general feature registry or analyzer/service interface hierarchy.
Ordinary functions accept concrete immutable data. Catalog and help providers
are callables because those are actual external-effect boundaries.

## Coordinate contract

- `TokenSpan.text` is a decoded shell word. Its `start/end`, command spans, and
  diagnostic issue spans are **code-point offsets in merged text**.
- `Document.original_offset` maps a merged boundary to the original source.
  `original_span` maps a half-open span without including a continuation that
  starts just after the span ends.
- `Document.positions` maps **original-source code points** to/from UTF-16
  columns. It indexes source lines once, including CRLF and bare CR boundaries.
- Only the LSP layer constructs wire positions/ranges, using `lsp.adapter` for
  coordinate conversion. Features must not subtract a Python string length
  from an LSP character column.
- Completion edits stay on the cursor's physical line. For a word continued
  from a preceding line, only candidates preserving the preceding prefix can
  be inserted with a single-line edit.

## Lifecycle and failure behavior

pygls updates its workspace before invoking open/change handlers. A request
gets the current source/version through `DocumentSession`; unchanged snapshots
are reused, and a changed source is reparsed even if a client repeats a version.
Only the most recent analysis is retained for each URI.

Open/change replaces that URI's diagnostic timer. Publication checks that the
document remains open at the scheduled version. Close cancels pending work,
removes cached analysis, and publishes an empty diagnostic list. Shutdown cancels
all timers and releases all cached analyses. State is per server, never global.

Analysis and provider calls are synchronous. Version checking is therefore
sufficient between scheduling and publication in the current event-loop model.
If these calls become asynchronous, recheck snapshot identity after the await;
do not publish results merely because a reopened document reused the version.

Errors are caught at the LSP boundary: completion returns an empty list, hover
returns no result, and CodeLens returns an empty list. A failed diagnostic run
is logged without preventing later updates. Non-QIIME documents do not load the
catalog; hover uses help independently of catalog availability.

## Changing behavior

- Add a completion rule in `core/completion.py`; test it with a source snapshot
  and a small `QiimeCatalog`, without starting a server.
- Add a command diagnostic in `command_analysis.py`, or a cross-command check
  in `document_level.py`. Keep issue codes stable and assign wire severity in
  `lsp/features.py`. Dependency extraction consumes valid option groups, not
  diagnostic display spans.
- Add another editor feature as a function over `Document`, render its response
  in `lsp/features.py`, and register the request in `lsp/server.py`. Only add a
  separate core module if the feature has analysis rules worth separating.
- Change shell syntax or source mapping in `core`, not separately in handlers.
  Check completion edits, diagnostic ranges, and CodeLens source slices together.

Tests under `tests/core/` cover the protocol-free analyzer and import boundary;
`tests/lsp/` cover rendering, cache/lifecycle behavior, and stdio round trips,
including incremental UTF-16 edits. Use the Pixi dev environment for pytest,
ruff, and pyright. `python -m pytest` / `python -m pyright` also work when local
console-script shebangs still point at a previous checkout location.

## Deliberate limits

This is still a lightweight shell/QIIME analyzer, not a complete POSIX shell
interpreter. Dynamic shell semantics, arbitrary nesting, and full quote-aware
completion editing are not newly promised by this refactor. Metadata discovery
and CLI help remain synchronous and retain their existing cache behavior; worker
processes, environment invalidation, and VS Code changes are separate work.

The inherited pygls protocol override is retained, not a pattern for new code:
pygls selects its workspace encoding before the user initialize handler runs.
Advertising UTF-16 without controlling that selection would corrupt incremental
edits when a client offers UTF-8 first. This framework-specific code is isolated
and protected by a wire-level test.
