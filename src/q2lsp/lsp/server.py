"""Composition root and LSP request registration; feature rules live elsewhere."""

from __future__ import annotations

import logging
from collections.abc import Callable

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from q2lsp.logging import get_logger
from q2lsp.lsp.error_handling import wrap_handler
from q2lsp.lsp.features import handle_code_lens, handle_completion, handle_hover
from q2lsp.lsp.protocol import Utf16LanguageServerProtocol
from q2lsp.lsp.session import DocumentSession
from q2lsp.qiime.catalog import CatalogProvider


def create_server(
    *,
    get_catalog: CatalogProvider,
    get_help: Callable[[list[str]], str | None],
    logger: logging.Logger | None = None,
    debounce_ms: int = 400,
) -> LanguageServer:
    logger = logger or get_logger("lsp")
    server = LanguageServer("q2lsp", "v0.1.0", protocol_cls=Utf16LanguageServerProtocol)
    session = DocumentSession(server, get_catalog, logger, debounce_ms)

    @server.feature(
        types.TEXT_DOCUMENT_COMPLETION,
        types.CompletionOptions(trigger_characters=[" ", "-"], resolve_provider=False),
    )
    @wrap_handler(
        logger=logger,
        feature_name=types.TEXT_DOCUMENT_COMPLETION,
        default_factory=lambda: types.CompletionList(is_incomplete=False, items=[]),
    )
    def completion(params: types.CompletionParams) -> types.CompletionList:
        return handle_completion(
            session.document(params.text_document.uri), params.position, get_catalog
        )

    @server.feature(
        types.TEXT_DOCUMENT_CODE_LENS, types.CodeLensOptions(resolve_provider=False)
    )
    @wrap_handler(
        logger=logger, feature_name=types.TEXT_DOCUMENT_CODE_LENS, default_factory=list
    )
    def code_lens(params: types.CodeLensParams) -> list[types.CodeLens]:
        uri = params.text_document.uri
        return handle_code_lens(session.document(uri), uri)

    @server.feature(types.TEXT_DOCUMENT_HOVER)
    @wrap_handler(
        logger=logger,
        feature_name=types.TEXT_DOCUMENT_HOVER,
        default_factory=lambda: None,
    )
    def hover(params: types.HoverParams) -> types.Hover | None:
        return handle_hover(
            session.document(params.text_document.uri), params.position, get_help
        )

    @server.feature(types.TEXT_DOCUMENT_DID_OPEN)
    @server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
    @wrap_handler(
        logger=logger,
        feature_name="diagnostics scheduling",
        default_factory=lambda: None,
    )
    def did_update(
        params: types.DidOpenTextDocumentParams | types.DidChangeTextDocumentParams,
    ) -> None:
        session.schedule_diagnostics(
            params.text_document.uri, params.text_document.version
        )

    @server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
    @wrap_handler(
        logger=logger,
        feature_name=types.TEXT_DOCUMENT_DID_CLOSE,
        default_factory=lambda: None,
    )
    def did_close(params: types.DidCloseTextDocumentParams) -> None:
        session.close(params.text_document.uri)

    @server.feature(types.SHUTDOWN)
    def shutdown(params: None = None) -> None:
        session.shutdown()

    return server
