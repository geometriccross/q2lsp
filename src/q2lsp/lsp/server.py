"""QIIME2 LSP Server using pygls 2.0.

Provides completion support for QIIME2 CLI commands in shell scripts.
"""

from __future__ import annotations

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
from q2lsp.lsp.adapter import (
    LSP_POSITION_ENCODING,
    offset_to_position as _offset_to_position,
    position_to_offset as _position_to_offset,
    to_lsp_completion_item as _to_lsp_completion_item,
)
from q2lsp.lsp.diagnostics import validate_command_with_catalog
from q2lsp.lsp.diagnostics.codes import DEFAULT_SEVERITY, DIAGNOSTIC_SEVERITY
from q2lsp.lsp.diagnostics.debounce import DebounceManager
from q2lsp.lsp.document_commands import (
    analyze_document,
    resolve_completion_context,
    to_original_offset,
)
from q2lsp.lsp.error_handling import wrap_async_handler, wrap_handler
from q2lsp.lsp.hover import get_hover_help
from q2lsp.qiime.catalog import make_catalog_provider
from q2lsp.qiime.hierarchy_provider import HierarchyProvider
from q2lsp.usecases.get_completions_usecase import (
    CompletionRequest,
    get_completions,
)


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
    get_hierarchy: HierarchyProvider,
    get_help: Callable[[list[str]], str | None] | None = None,
    logger: logging.Logger | None = None,
    debounce_ms: int = 400,
) -> LanguageServer:
    """
    Create and configure the LSP server.

    Args:
        get_hierarchy: Provider function for QIIME2 command hierarchy.
        get_help: Provider function for hover help text (takes command path).
        logger: Optional logger instance. If None, uses default q2lsp.lsp logger.
        debounce_ms: Debounce delay in milliseconds for diagnostics. Default 400.

    Returns:
        Configured LanguageServer instance with completion support.
    """
    if logger is None:
        logger = get_logger("lsp")

    server = LanguageServer("q2lsp", "v0.1.0", protocol_cls=Utf16LanguageServerProtocol)
    debounce_manager = DebounceManager()
    get_catalog = make_catalog_provider(get_hierarchy)

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

        # Calculate document offset from line/character position
        offset = _position_to_offset(document, params.position)

        # Analyze document and get completion context
        doc = analyze_document(document.source)
        ctx = resolve_completion_context(doc, offset)
        logger.debug("Completion context: mode=%s, prefix=%s", ctx.mode, ctx.prefix)

        # Get completion items
        command_tokens: tuple[str, ...] = ()
        if ctx.command is not None:
            command_tokens = tuple(token.text for token in ctx.command.tokens)
        request = CompletionRequest(
            mode=str(ctx.mode),
            prefix=ctx.prefix,
            command_tokens=command_tokens,
        )
        internal_items = get_completions(request, get_catalog())

        # Convert to LSP CompletionItems
        lsp_items = [
            _to_lsp_completion_item(item, position=params.position, prefix=ctx.prefix)
            for item in internal_items
        ]

        logger.debug("Returning %d completion items", len(lsp_items))
        return types.CompletionList(
            is_incomplete=False,
            items=lsp_items,
        )

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

        # Calculate document offset from line/character position
        offset = _position_to_offset(document, params.position)

        # Analyze document and get hover help
        doc = analyze_document(document.source)
        ctx = resolve_completion_context(doc, offset)
        catalog = get_catalog() if get_help is None else None
        help_text = get_hover_help(ctx, get_help=get_help, catalog=catalog)

        if help_text is None:
            return None

        logger.debug("Hover help: %s", help_text[:100])
        return types.Hover(
            contents=types.MarkupContent(
                kind=types.MarkupKind.Markdown,
                value=f"```\n{help_text}\n```",
            ),
        )

    # Diagnostics
    async def publish_document_diagnostics(
        uri: str, document_version: int | None
    ) -> None:
        """
        Publish diagnostics for a document.

        This function is called after debounce.
        """
        # Check if document still exists
        document = server.workspace.get_text_document(uri)
        if document is None:
            return

        # Check version to avoid publishing stale results
        if document_version is not None and document.version != document_version:
            logger.debug(
                "Skipping diagnostics for %s: version mismatch (expected %s, got %s)",
                uri,
                document_version,
                document.version,
            )
            return

        try:
            # Analyze document
            doc = analyze_document(document.source)

            catalog = get_catalog()

            # Validate each command
            lsp_diagnostics: list[types.Diagnostic] = []
            for cmd in doc.commands:
                issues = validate_command_with_catalog(cmd, catalog)
                for issue in issues:
                    # Map merged offsets back to original offsets
                    original_start = to_original_offset(doc, issue.start)
                    original_end = to_original_offset(doc, issue.end)

                # Convert offsets to LSP position
                start_pos = _offset_to_position(document, original_start)
                end_pos = _offset_to_position(document, original_end)

                lsp_diagnostics.append(
                    types.Diagnostic(
                        range=types.Range(start=start_pos, end=end_pos),
                        message=issue.message,
                        severity=DIAGNOSTIC_SEVERITY.get(issue.code, DEFAULT_SEVERITY),
                        source="q2lsp",
                        code=issue.code,
                    )
                )

            # Publish diagnostics using pygls standard method
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

    @server.feature(types.TEXT_DOCUMENT_DID_OPEN)
    @wrap_async_handler(
        logger=logger,
        feature_name="textDocument/didOpen",
        default_factory=lambda: None,
    )
    async def did_open(params: types.DidOpenTextDocumentParams) -> None:
        """Handle textDocument/didOpen by scheduling diagnostics."""
        uri = params.text_document.uri
        document = server.workspace.get_text_document(uri)
        if document is None:
            return

        logger.debug("Document opened: %s (version %s)", uri, document.version)

        # Schedule diagnostics with debounce
        await debounce_manager.schedule(
            uri,
            lambda: publish_document_diagnostics(uri, document.version),
            delay_ms=debounce_ms,
        )

    @server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
    @wrap_async_handler(
        logger=logger,
        feature_name="textDocument/didChange",
        default_factory=lambda: None,
    )
    async def did_change(params: types.DidChangeTextDocumentParams) -> None:
        """Handle textDocument/didChange by debouncing diagnostics."""
        uri = params.text_document.uri
        document = server.workspace.get_text_document(uri)
        if document is None:
            return

        logger.debug("Document changed: %s (version %s)", uri, document.version)

        # Schedule diagnostics with debounce
        await debounce_manager.schedule(
            uri,
            lambda: publish_document_diagnostics(uri, document.version),
            delay_ms=debounce_ms,
        )

    @server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
    @wrap_async_handler(
        logger=logger,
        feature_name="textDocument/didClose",
        default_factory=lambda: None,
    )
    async def did_close(params: types.DidCloseTextDocumentParams) -> None:
        """Handle textDocument/didClose by clearing diagnostics."""
        uri = params.text_document.uri

        logger.debug("Document closed: %s", uri)

        # Clear diagnostics
        server.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(
                uri=uri,
                diagnostics=[],
                version=None,
            )
        )

        # Cancel any pending validation task
        await debounce_manager.cancel(uri)

    return server
