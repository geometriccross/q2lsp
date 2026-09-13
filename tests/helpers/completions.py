"""Completion helpers using production document analysis."""

from __future__ import annotations

from q2lsp.core.types import CompletionItem
from q2lsp.lsp.completion import get_completions
from q2lsp.lsp.document_commands import analyze_document, resolve_completion_context
from q2lsp.lsp.types import CompletionContext
from q2lsp.qiime.catalog import QiimeCatalog


def get_completion_context(text: str, offset: int) -> CompletionContext:
    return resolve_completion_context(analyze_document(text), offset)


def complete(source: str, catalog: QiimeCatalog) -> list[CompletionItem]:
    return get_completions(get_completion_context(source, len(source)), catalog)
