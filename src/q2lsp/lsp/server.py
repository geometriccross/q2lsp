"""QIIME2 LSP Server using pygls 2.0.

Provides completion support for QIIME2 CLI commands in shell scripts.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Generator
from typing import Any

from lsprotocol import types
from pygls.capabilities import ServerCapabilitiesBuilder
from pygls.lsp.server import LanguageServer
from pygls.protocol import LanguageServerProtocol
from pygls.protocol.language_server import lsp_method
from pygls.uris import from_fs_path
from pygls.workspace import Workspace

from q2lsp.logging import get_logger
from q2lsp.lsp.adapter import LSP_POSITION_ENCODING
from q2lsp.lsp.code_lens_handler import handle_code_lens
from q2lsp.lsp.completion_handler import handle_completion
from q2lsp.lsp.diagnostics_handler import compute_diagnostics
from q2lsp.lsp.error_handling import wrap_handler
from q2lsp.lsp.hover_handler import handle_hover
from q2lsp.qiime.catalog import CatalogProvider


class Utf16LanguageServerProtocol(LanguageServerProtocol):
    """Language server protocol that keeps q2lsp wire positions UTF-16."""

    @lsp_method(types.INITIALIZE)
    def lsp_initialize(
        self, params: types.InitializeParams
    ) -> Generator[Any, Any, types.InitializeResult]:
        """Initialize while pinning pygls' position encoding to UTF-16."""
        self._server.process_id = params.process_id

        text_document_sync_kind = self._server._text_document_sync_kind
        notebook_document_sync = self._server._notebook_document_sync

        self.client_capabilities = params.capabilities
        position_encoding = LSP_POSITION_ENCODING

        root_path = params.root_path
        root_uri = params.root_uri
        if root_path is not None and root_uri is None:
            root_uri = from_fs_path(root_path)

        workspace_folders = params.workspace_folders or []
        self._workspace = Workspace(
            root_uri,
            text_document_sync_kind,
            workspace_folders,
            position_encoding,
        )

        if (user_handler := self.fm.features.get(types.INITIALIZE)) is not None:
            yield user_handler, (params,), None

        self.server_capabilities = ServerCapabilitiesBuilder(
            self.client_capabilities,
            set({**self.fm.features, **self.fm.builtin_features}.keys()),
            self.fm.feature_options,
            list(self.fm.commands.keys()),
            text_document_sync_kind,
            notebook_document_sync,
            position_encoding,
        ).build()

        return types.InitializeResult(
            capabilities=self.server_capabilities,
            server_info=self.server_info,
        )


def create_server(
    *,
    get_catalog: CatalogProvider,
    get_help: Callable[[list[str]], str | None],
    logger: logging.Logger | None = None,
    debounce_ms: int = 400,
) -> LanguageServer:
    """
    Create and configure the LSP server.

    Args:
        get_catalog: Provider function for QIIME2 command catalog.
        get_help: Provider function for hover help text (takes command path).
        logger: Optional logger instance. If None, uses default q2lsp.lsp logger.
        debounce_ms: Debounce delay in milliseconds for diagnostics. Default 400.

    Returns:
        Configured LanguageServer instance with completion support.
    """
    if logger is None:
        logger = get_logger("lsp")

    server = LanguageServer("q2lsp", "v0.1.0", protocol_cls=Utf16LanguageServerProtocol)
    pending_diagnostics: dict[str, asyncio.TimerHandle] = {}

    def _empty_completion_list() -> types.CompletionList:
        return types.CompletionList(is_incomplete=False, items=[])

    @server.feature(
        types.TEXT_DOCUMENT_COMPLETION,
        types.CompletionOptions(
            trigger_characters=[" ", "-"],
            resolve_provider=False,
        ),
    )
    @wrap_handler(
        logger=logger,
        feature_name="textDocument/completion",
        default_factory=_empty_completion_list,
    )
    def completion(params: types.CompletionParams) -> types.CompletionList:
        """
        Handle textDocument/completion requests.

        Provides completion for QIIME2 CLI commands in shell scripts.
        """
        logger.debug("Completion request at %s", params.position)

        document = server.workspace.get_text_document(params.text_document.uri)
        result = handle_completion(document, params.position, get_catalog)

        logger.debug("Returning %d completion items", len(result.items))
        return result

    def _empty_code_lens_list() -> list[types.CodeLens]:
        return []

    @server.feature(
        types.TEXT_DOCUMENT_CODE_LENS,
        types.CodeLensOptions(resolve_provider=False),
    )
    @wrap_handler(
        logger=logger,
        feature_name="textDocument/codeLens",
        default_factory=_empty_code_lens_list,
    )
    def code_lens(params: types.CodeLensParams) -> list[types.CodeLens]:
        """Handle textDocument/codeLens requests for runnable QIIME commands."""
        logger.debug("CodeLens request for %s", params.text_document.uri)

        document = server.workspace.get_text_document(params.text_document.uri)
        result = handle_code_lens(document)

        logger.debug("Returning %d CodeLens items", len(result))
        return result

    def _default_hover() -> types.Hover | None:
        return None

    @server.feature(types.TEXT_DOCUMENT_HOVER)
    @wrap_handler(
        logger=logger,
        feature_name="textDocument/hover",
        default_factory=_default_hover,
    )
    def hover(params: types.HoverParams) -> types.Hover | None:  # type: ignore[misc]
        """
        Handle textDocument/hover requests.

        Provides hover help for QIIME2 CLI commands.
        """
        logger.debug("Hover request at %s", params.position)

        document = server.workspace.get_text_document(params.text_document.uri)

        return handle_hover(document, params.position, get_help)

    def publish_document_diagnostics(uri: str, document_version: int) -> None:
        pending_diagnostics.pop(uri, None)
        try:
            document = server.workspace.text_documents.get(uri)
            if document is None or document.version != document_version:
                return

            lsp_diagnostics = compute_diagnostics(document, get_catalog)
            server.text_document_publish_diagnostics(
                types.PublishDiagnosticsParams(
                    uri=uri,
                    diagnostics=lsp_diagnostics,
                    version=document_version,
                )
            )
            logger.debug(
                "Published %d diagnostics for %s (version %s)",
                len(lsp_diagnostics),
                uri,
                document_version,
            )
        except Exception:
            logger.exception("Error publishing diagnostics for %s", uri)

    def cancel_diagnostics(uri: str) -> None:
        if timer := pending_diagnostics.pop(uri, None):
            timer.cancel()

    @server.feature(types.TEXT_DOCUMENT_DID_OPEN)
    @server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
    @wrap_handler(
        logger=logger,
        feature_name="diagnostics scheduling",
        default_factory=lambda: None,
    )
    def schedule_diagnostics(
        params: types.DidOpenTextDocumentParams | types.DidChangeTextDocumentParams,
    ) -> None:
        uri = params.text_document.uri
        cancel_diagnostics(uri)
        pending_diagnostics[uri] = asyncio.get_running_loop().call_later(
            debounce_ms / 1000,
            publish_document_diagnostics,
            uri,
            params.text_document.version,
        )

    @server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
    @wrap_handler(
        logger=logger,
        feature_name="textDocument/didClose",
        default_factory=lambda: None,
    )
    def did_close(params: types.DidCloseTextDocumentParams) -> None:
        uri = params.text_document.uri
        cancel_diagnostics(uri)
        server.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(uri=uri, diagnostics=[], version=None)
        )

    @server.feature(types.SHUTDOWN)
    def shutdown(params: None = None) -> None:
        for timer in pending_diagnostics.values():
            timer.cancel()
        pending_diagnostics.clear()

    return server
