"""Per-server document analysis cache and diagnostic lifecycle.

pygls owns source text and versions. This session owns only derived snapshots
and pending work; closing a document releases both.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from lsprotocol import types
from pygls.lsp.server import LanguageServer
from pygls.workspace import TextDocument

from q2lsp.core.document import Document, analyze_document
from q2lsp.lsp.features import compute_diagnostics
from q2lsp.qiime.catalog import CatalogProvider


@dataclass
class DocumentSession:
    server: LanguageServer
    get_catalog: CatalogProvider
    logger: logging.Logger
    debounce_ms: int = 400
    _documents: dict[str, tuple[int | None, Document]] = field(
        default_factory=dict, init=False
    )
    _pending: dict[str, asyncio.TimerHandle] = field(default_factory=dict, init=False)

    def document(self, uri: str) -> Document:
        return self._analyze(self.server.workspace.get_text_document(uri))

    def _analyze(self, document: TextDocument) -> Document:
        cached = self._documents.get(document.uri)
        if cached is not None:
            version, analysis = cached
            if version == document.version and analysis.source == document.source:
                return analysis
        analysis = analyze_document(document.source)
        self._documents[document.uri] = (document.version, analysis)
        return analysis

    def schedule_diagnostics(self, uri: str, version: int) -> None:
        self._cancel(uri)
        self._pending[uri] = asyncio.get_running_loop().call_later(
            self.debounce_ms / 1000, self._publish_diagnostics, uri, version
        )

    def _publish_diagnostics(self, uri: str, version: int) -> None:
        self._pending.pop(uri, None)
        try:
            document = self.server.workspace.text_documents.get(uri)
            if document is None or document.version != version:
                return
            diagnostics = compute_diagnostics(self._analyze(document), self.get_catalog)
            self.server.text_document_publish_diagnostics(
                types.PublishDiagnosticsParams(
                    uri=uri, diagnostics=diagnostics, version=version
                )
            )
        except Exception:
            self.logger.exception("Error publishing diagnostics for %s", uri)

    def close(self, uri: str) -> None:
        self._cancel(uri)
        self._documents.pop(uri, None)
        self.server.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(uri=uri, diagnostics=[], version=None)
        )

    def shutdown(self) -> None:
        for timer in self._pending.values():
            timer.cancel()
        self._pending.clear()
        self._documents.clear()

    def _cancel(self, uri: str) -> None:
        if timer := self._pending.pop(uri, None):
            timer.cancel()
