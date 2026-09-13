"""Completion helpers using production document analysis."""

from __future__ import annotations

from q2lsp.core.types import CompletionItem
from q2lsp.core.completion import get_completions
from q2lsp.core.document import CursorContext, analyze_document
from q2lsp.qiime.catalog import QiimeCatalog


def get_completion_context(text: str, offset: int) -> CursorContext:
    return analyze_document(text).cursor_at(offset)


def complete(source: str, catalog: QiimeCatalog) -> list[CompletionItem]:
    return get_completions(get_completion_context(source, len(source)), catalog)
