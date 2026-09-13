"""Compatibility boundary for pygls' UTF-16 workspace initialization."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from lsprotocol import types
from pygls.capabilities import ServerCapabilitiesBuilder
from pygls.protocol import LanguageServerProtocol
from pygls.protocol.language_server import lsp_method
from pygls.uris import from_fs_path
from pygls.workspace import Workspace

from q2lsp.lsp.adapter import LSP_POSITION_ENCODING


class Utf16LanguageServerProtocol(LanguageServerProtocol):
    """Existing pygls override, isolated here because it uses framework internals.

    pygls chooses the workspace encoding before calling the user initialize
    handler. Setting only the advertised capability there would leave incremental
    document edits using a different encoding from q2lsp's source mapper.
    """

    @lsp_method(types.INITIALIZE)
    def lsp_initialize(
        self, params: types.InitializeParams
    ) -> Generator[Any, Any, types.InitializeResult]:
        self._server.process_id = params.process_id
        text_document_sync_kind = self._server._text_document_sync_kind
        notebook_document_sync = self._server._notebook_document_sync
        self.client_capabilities = params.capabilities

        root_uri = params.root_uri
        if params.root_path is not None and root_uri is None:
            root_uri = from_fs_path(params.root_path)
        self._workspace = Workspace(
            root_uri,
            text_document_sync_kind,
            params.workspace_folders or [],
            LSP_POSITION_ENCODING,
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
            LSP_POSITION_ENCODING,
        ).build()
        return types.InitializeResult(
            capabilities=self.server_capabilities,
            server_info=self.server_info,
        )
