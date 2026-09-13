"""Editor responses over a shared, immutable document analysis.

These functions do not read the workspace, parse documents, or own mutable state.
Catalog and help discovery remain lazy and independent of one another.
"""

from __future__ import annotations

from collections.abc import Callable

from lsprotocol import types

from q2lsp.core.completion import get_completions
from q2lsp.core.diagnostics import collect_diagnostics, codes
from q2lsp.core.document import Document
from q2lsp.lsp.adapter import (
    merged_range,
    offset_to_position,
    position_to_offset,
    to_lsp_completion_item,
)
from q2lsp.qiime.catalog import CatalogProvider

_ERROR_CODES = {
    codes.MISSING_REQUIRED_OPTION,
    codes.DEPENDENCY_CYCLE,
    codes.DUPLICATE_OUTPUT_PATH,
}


def handle_completion(
    document: Document, position: types.Position, get_catalog: CatalogProvider
) -> types.CompletionList:
    offset = position_to_offset(document, position)
    context = document.cursor_at(offset)
    if context.command is None or context.token_index < 1:
        return types.CompletionList(is_incomplete=False, items=[])

    edit_range = None
    retained_prefix = ""
    if context.current_token is not None and context.prefix:
        token_start = document.original_offset(context.prefix_start)
        line_start = document.positions.position_to_offset(position.line, 0)
        start = max(token_start, line_start)
        # Completion TextEdits must stay on the request's line. A word may start
        # on an earlier line, so preserve its already-typed prefix there.
        retained_prefix = document.cursor_at(start).prefix
        edit_range = types.Range(
            start=offset_to_position(document, start),
            end=offset_to_position(document, offset),
        )

    return types.CompletionList(
        is_incomplete=False,
        items=[
            to_lsp_completion_item(item, edit_range, retained_prefix=retained_prefix)
            for item in get_completions(context, get_catalog())
            if (item.insert_text or item.label).startswith(retained_prefix)
        ],
    )


def handle_hover(
    document: Document,
    position: types.Position,
    get_help: Callable[[list[str]], str | None],
) -> types.Hover | None:
    context = document.cursor_at(position_to_offset(document, position))
    if context.command is None or context.current_token is None:
        return None
    if not 0 <= context.token_index <= 2:
        return None
    path = [token.text for token in context.command.tokens[1 : context.token_index + 1]]
    help_text = get_help(path)
    if help_text is None:
        return None
    return types.Hover(
        contents=types.MarkupContent(
            kind=types.MarkupKind.Markdown, value=f"```\n{help_text}\n```"
        )
    )


def handle_code_lens(document: Document, uri: str) -> list[types.CodeLens]:
    return [
        types.CodeLens(
            range=merged_range(
                document, command.tokens[0].start, command.tokens[0].end
            ),
            command=types.Command(
                title="Run QIIME command",
                command="q2lsp.runCommand",
                arguments=[
                    {
                        "uri": uri,
                        "commandText": document.command_text(command),
                        "tokens": [token.text for token in command.tokens],
                    }
                ],
            ),
        )
        for command in document.commands
    ]


def compute_diagnostics(
    document: Document, get_catalog: CatalogProvider
) -> list[types.Diagnostic]:
    if not document.commands:
        return []
    return [
        types.Diagnostic(
            range=merged_range(document, issue.start, issue.end),
            message=issue.message,
            severity=types.DiagnosticSeverity.Error
            if issue.code in _ERROR_CODES
            else types.DiagnosticSeverity.Warning,
            source="q2lsp",
            code=issue.code,
        )
        for issue in collect_diagnostics(document, get_catalog())
    ]
