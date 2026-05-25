"""Standalone textDocument/codeLens handler behavior."""

from __future__ import annotations

from lsprotocol import types
from pygls.workspace import TextDocument

from q2lsp.lsp.adapter import offset_to_position
from q2lsp.lsp.document_commands import analyze_document, to_original_offset


def handle_code_lens(
    document: TextDocument,
) -> list[types.CodeLens]:
    """Return runnable QIIME command code lenses for a document."""
    doc = analyze_document(document.source)

    code_lenses: list[types.CodeLens] = []
    for command in doc.commands:
        qiime_token = command.tokens[0]
        original_start = to_original_offset(doc, qiime_token.start)
        original_end = to_original_offset(doc, qiime_token.end)
        command_start = to_original_offset(doc, command.start)
        command_end = to_original_offset(doc, command.end)
        code_lenses.append(
            types.CodeLens(
                range=types.Range(
                    start=offset_to_position(document, original_start),
                    end=offset_to_position(document, original_end),
                ),
                command=types.Command(
                    title="Run QIIME command",
                    command="q2lsp.runCommand",
                    arguments=[
                        {
                            "uri": document.uri,
                            "commandText": document.source[command_start:command_end],
                            "tokens": [token.text for token in command.tokens],
                        }
                    ],
                ),
            )
        )

    return code_lenses
