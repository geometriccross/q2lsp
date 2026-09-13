"""Server request routing and failure responses."""

from __future__ import annotations

import pytest
from lsprotocol import types
from pygls.lsp.server import LanguageServer
from pygls.workspace import Workspace

from q2lsp.lsp.server import create_server
from q2lsp.qiime.catalog import QiimeCatalog


@pytest.fixture
def server() -> LanguageServer:
    catalog = QiimeCatalog.from_hierarchy({"qiime": {"feature-table": {}}})
    server = create_server(
        get_catalog=lambda: catalog, get_help=lambda _path: "Root help"
    )
    server.protocol._workspace = Workspace(None)
    server.workspace.put_text_document(
        types.TextDocumentItem(
            uri="file:///test.sh",
            language_id="shellscript",
            version=1,
            text="qiime feat",
        )
    )
    return server


def test_completion_routes_document_and_cursor(server: LanguageServer) -> None:
    result = server.protocol.fm.features[types.TEXT_DOCUMENT_COMPLETION](
        types.CompletionParams(
            text_document=types.TextDocumentIdentifier("file:///test.sh"),
            position=types.Position(0, 10),
        )
    )
    assert [item.label for item in result.items] == ["feature-table"]
    assert result.items[0].text_edit == types.TextEdit(
        range=types.Range(start=types.Position(0, 6), end=types.Position(0, 10)),
        new_text="feature-table",
    )


@pytest.mark.parametrize(
    ("feature", "params", "expected"),
    [
        (
            types.TEXT_DOCUMENT_COMPLETION,
            types.CompletionParams(
                text_document=types.TextDocumentIdentifier("file:///test.sh"),
                position=types.Position(0, 0),
            ),
            types.CompletionList(is_incomplete=False, items=[]),
        ),
        (
            types.TEXT_DOCUMENT_HOVER,
            types.HoverParams(
                text_document=types.TextDocumentIdentifier("file:///test.sh"),
                position=types.Position(0, 0),
            ),
            None,
        ),
        (
            types.TEXT_DOCUMENT_CODE_LENS,
            types.CodeLensParams(
                text_document=types.TextDocumentIdentifier("file:///test.sh")
            ),
            [],
        ),
    ],
)
def test_request_failures_return_feature_defaults(
    server: LanguageServer,
    monkeypatch: pytest.MonkeyPatch,
    feature: str,
    params: types.CompletionParams | types.HoverParams | types.CodeLensParams,
    expected: types.CompletionList | list[types.CodeLens] | None,
) -> None:
    def fail_document(_uri: str) -> None:
        raise RuntimeError("workspace unavailable")

    monkeypatch.setattr(server.workspace, "get_text_document", fail_document)
    assert server.protocol.fm.features[feature](params) == expected


def test_hover_uses_help_without_loading_catalog() -> None:
    def fail_catalog() -> QiimeCatalog:
        raise AssertionError("Hover must not load the completion catalog")

    server = create_server(
        get_catalog=fail_catalog, get_help=lambda path: f"Help for {path}"
    )
    server.protocol._workspace = Workspace(None)
    server.workspace.put_text_document(
        types.TextDocumentItem(
            uri="file:///test.sh",
            language_id="shellscript",
            version=1,
            text="qiime info",
        )
    )
    result = server.protocol.fm.features[types.TEXT_DOCUMENT_HOVER](
        types.HoverParams(
            text_document=types.TextDocumentIdentifier("file:///test.sh"),
            position=types.Position(0, 8),
        )
    )
    assert result == types.Hover(
        contents=types.MarkupContent(
            kind=types.MarkupKind.Markdown, value="```\nHelp for ['info']\n```"
        ),
    )
