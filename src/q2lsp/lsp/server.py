"""QIIME2 LSP Server using pygls 2.0.

Provides completion support for QIIME2 CLI commands in shell scripts.
"""

from __future__ import annotations

import logging
from typing import Callable

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from q2lsp.logging import get_logger
from q2lsp.lsp.adapter import (
    offset_to_position as _offset_to_position,
    position_to_offset as _position_to_offset,
    to_lsp_completion_item as _to_lsp_completion_item,
)
from q2lsp.lsp.diagnostics import collect_diagnostics
from q2lsp.lsp.diagnostics.codes import DEFAULT_SEVERITY, DIAGNOSTIC_SEVERITY
from q2lsp.lsp.diagnostics.debounce import DebounceManager
from q2lsp.lsp.document_commands import (
    analyze_document,
    resolve_completion_context,
    to_original_offset,
)
from q2lsp.lsp.error_handling import wrap_async_handler, wrap_handler
from q2lsp.lsp.hover import get_hover_help
from q2lsp.qiime.hierarchy_provider import HierarchyProvider
from q2lsp.usecases.get_completions_usecase import CompletionRequest, get_completions


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

    server = LanguageServer("q2lsp", "v0.1.0")
    debounce_manager = DebounceManager()

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
        hierarchy = get_hierarchy()
        command_tokens: tuple[str, ...] = ()
        if ctx.command is not None:
            command_tokens = tuple(token.text for token in ctx.command.tokens)
        request = CompletionRequest(
            mode=str(ctx.mode),
            prefix=ctx.prefix,
            command_tokens=command_tokens,
        )
        internal_items = get_completions(request, hierarchy)

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
        help_text = get_hover_help(ctx, get_help=get_help)

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
            # Get hierarchy
            hierarchy = get_hierarchy()

            # Analyze document
            doc = analyze_document(document.source)

            # Collect diagnostics
            lsp_diagnostics: list[types.Diagnostic] = []
            for issue in collect_diagnostics(doc, hierarchy):
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
