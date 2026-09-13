"""Diagnostic publishing and document lifecycle with real workspace documents."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from lsprotocol import types
from pygls.lsp.server import LanguageServer
from pygls.workspace import Workspace

import q2lsp.lsp.server as server_mod
import q2lsp.lsp.session as session_mod
from q2lsp.core.diagnostics.codes import MISSING_REQUIRED_OPTION, UNKNOWN_OPTION
from q2lsp.core.document import Document
from q2lsp.qiime.catalog import make_catalog_provider
from q2lsp.qiime.types import CommandHierarchy

DEBOUNCE_MS = 10
URI = "file:///test.sh"


@pytest.fixture
def hierarchy() -> CommandHierarchy:
    return {
        "qiime": {
            "demo": {
                "step": {
                    "signature": [
                        {"name": "table", "type": "input"},
                        {"name": "metadata", "type": "metadata"},
                    ]
                }
            }
        }
    }


@pytest.fixture
def server_and_published(
    hierarchy: CommandHierarchy,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[LanguageServer, asyncio.Queue[types.PublishDiagnosticsParams]]]:
    server = server_mod.create_server(
        get_catalog=make_catalog_provider(lambda: hierarchy),
        get_help=lambda _path: None,
        debounce_ms=DEBOUNCE_MS,
    )
    server.protocol._workspace = Workspace(None)
    published: asyncio.Queue[types.PublishDiagnosticsParams] = asyncio.Queue()
    monkeypatch.setattr(
        server, "text_document_publish_diagnostics", published.put_nowait
    )
    yield server, published
    server.protocol.fm.features[types.SHUTDOWN](None)


def open_document(server: LanguageServer, source: str, uri: str = URI) -> None:
    document = types.TextDocumentItem(
        uri=uri, language_id="shellscript", version=1, text=source
    )
    server.workspace.put_text_document(document)
    server.protocol.fm.features[types.TEXT_DOCUMENT_DID_OPEN](
        types.DidOpenTextDocumentParams(document)
    )


def change_document(server: LanguageServer, source: str, version: int) -> None:
    identifier = types.VersionedTextDocumentIdentifier(uri=URI, version=version)
    change = types.TextDocumentContentChangeWholeDocument(text=source)
    server.workspace.update_text_document(identifier, change)
    server.protocol.fm.features[types.TEXT_DOCUMENT_DID_CHANGE](
        types.DidChangeTextDocumentParams(
            text_document=identifier, content_changes=[change]
        )
    )


def close_document(server: LanguageServer, uri: str = URI) -> None:
    server.workspace.remove_text_document(uri)
    server.protocol.fm.features[types.TEXT_DOCUMENT_DID_CLOSE](
        types.DidCloseTextDocumentParams(types.TextDocumentIdentifier(uri))
    )


async def wait_past_debounce() -> None:
    await asyncio.sleep(DEBOUNCE_MS / 1000 * 3)


async def test_open_publishes_diagnostic_ranges_and_severity(
    server_and_published: tuple[
        LanguageServer, asyncio.Queue[types.PublishDiagnosticsParams]
    ],
) -> None:
    server, published = server_and_published
    source = "qiime demo step --unknown-opt value"
    open_document(server, source)
    result = await asyncio.wait_for(published.get(), timeout=1)

    assert result.uri == URI
    assert result.version == 1
    assert [issue.code for issue in result.diagnostics] == [
        UNKNOWN_OPTION,
        MISSING_REQUIRED_OPTION,
        MISSING_REQUIRED_OPTION,
    ]
    unknown, *missing = result.diagnostics
    start = source.index("--unknown-opt")
    assert unknown.range == types.Range(
        start=types.Position(0, start), end=types.Position(0, start + 13)
    )
    assert unknown.severity == types.DiagnosticSeverity.Warning
    assert all(issue.severity == types.DiagnosticSeverity.Error for issue in missing)


async def test_rapid_changes_publish_only_the_latest_version(
    server_and_published: tuple[
        LanguageServer, asyncio.Queue[types.PublishDiagnosticsParams]
    ],
) -> None:
    server, published = server_and_published
    open_document(server, "qiime unknown")
    change_document(server, "qiime demo step --bad", 2)
    change_document(
        server, "qiime demo step --i-table table.qza --m-metadata metadata.tsv", 3
    )
    result = await asyncio.wait_for(published.get(), timeout=1)

    assert result.version == 3
    assert result.diagnostics == []
    await wait_past_debounce()
    assert published.empty()


async def test_document_timers_are_independent(
    server_and_published: tuple[
        LanguageServer, asyncio.Queue[types.PublishDiagnosticsParams]
    ],
) -> None:
    server, published = server_and_published
    open_document(server, "qiime unknown")
    open_document(server, "qiime other", "file:///other.sh")
    results = [await asyncio.wait_for(published.get(), timeout=1) for _ in range(2)]
    assert {result.uri for result in results} == {URI, "file:///other.sh"}
    assert all(result.diagnostics for result in results)


async def test_close_clears_diagnostics_and_cancels_pending_work(
    server_and_published: tuple[
        LanguageServer, asyncio.Queue[types.PublishDiagnosticsParams]
    ],
) -> None:
    server, published = server_and_published
    open_document(server, "qiime unknown")
    close_document(server)
    assert published.get_nowait() == types.PublishDiagnosticsParams(
        uri=URI, diagnostics=[], version=None
    )
    await wait_past_debounce()
    assert published.empty()


async def test_reopening_same_uri_does_not_publish_the_old_document(
    server_and_published: tuple[
        LanguageServer, asyncio.Queue[types.PublishDiagnosticsParams]
    ],
) -> None:
    server, published = server_and_published
    open_document(server, "qiime unknown")
    close_document(server)
    published.get_nowait()
    open_document(server, "echo hello")
    result = await asyncio.wait_for(published.get(), timeout=1)
    assert result.version == 1
    assert result.diagnostics == []
    await wait_past_debounce()
    assert published.empty()


@pytest.mark.parametrize("remove_document", [False, True])
async def test_outdated_or_missing_document_is_not_published(
    server_and_published: tuple[
        LanguageServer, asyncio.Queue[types.PublishDiagnosticsParams]
    ],
    remove_document: bool,
) -> None:
    server, published = server_and_published
    open_document(server, "qiime unknown")
    if remove_document:
        server.workspace.remove_text_document(URI)
    else:
        server.workspace.get_text_document(URI).version = 2
    await wait_past_debounce()
    assert published.empty()


async def test_shutdown_cancels_pending_diagnostics(
    server_and_published: tuple[
        LanguageServer, asyncio.Queue[types.PublishDiagnosticsParams]
    ],
) -> None:
    server, published = server_and_published
    open_document(server, "qiime unknown")
    server.protocol.fm.features[types.SHUTDOWN](None)
    await wait_past_debounce()
    assert published.empty()


async def test_failed_diagnostics_do_not_prevent_later_updates(
    server_and_published: tuple[
        LanguageServer, asyncio.Queue[types.PublishDiagnosticsParams]
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, published = server_and_published
    with monkeypatch.context() as patch:

        def fail(*_args: object) -> list[types.Diagnostic]:
            raise RuntimeError("temporary discovery failure")

        patch.setattr(session_mod, "compute_diagnostics", fail)
        open_document(server, "qiime unknown")
        await wait_past_debounce()
        assert published.empty()

    change_document(server, "qiime unknown", 2)
    result = await asyncio.wait_for(published.get(), timeout=1)
    assert result.version == 2
    assert result.diagnostics


async def test_all_features_reuse_analysis_until_the_document_changes(
    server_and_published: tuple[
        LanguageServer, asyncio.Queue[types.PublishDiagnosticsParams]
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, published = server_and_published
    analyses: list[Document] = []
    analyze = session_mod.analyze_document

    def track(source: str) -> Document:
        document = analyze(source)
        analyses.append(document)
        return document

    monkeypatch.setattr(session_mod, "analyze_document", track)
    open_document(server, "qiime demo step --bad")
    features = server.protocol.fm.features
    assert features[types.TEXT_DOCUMENT_COMPLETION](
        types.CompletionParams(types.TextDocumentIdentifier(URI), types.Position(0, 8))
    ).items
    features[types.TEXT_DOCUMENT_HOVER](
        types.HoverParams(types.TextDocumentIdentifier(URI), types.Position(0, 8))
    )
    assert features[types.TEXT_DOCUMENT_CODE_LENS](
        types.CodeLensParams(types.TextDocumentIdentifier(URI))
    )
    assert (await asyncio.wait_for(published.get(), timeout=1)).diagnostics
    assert len(analyses) == 1

    change_document(server, "echo hello", 2)
    assert (
        features[types.TEXT_DOCUMENT_CODE_LENS](
            types.CodeLensParams(types.TextDocumentIdentifier(URI))
        )
        == []
    )
    assert (await asyncio.wait_for(published.get(), timeout=1)).diagnostics == []
    assert len(analyses) == 2
    assert analyses[0].source == "qiime demo step --bad"
    assert analyses[1].source == "echo hello"

    close_document(server)
    published.get_nowait()
    open_document(server, "echo hello")
    await asyncio.wait_for(published.get(), timeout=1)
    assert len(analyses) == 3
    assert analyses[2] is not analyses[1]
    close_document(server)
    published.get_nowait()
    open_document(server, "echo hello")
    await asyncio.wait_for(published.get(), timeout=1)
    assert len(analyses) == 4
    assert analyses[3] is not analyses[2]


async def test_continuation_diagnostic_uses_original_line(
    server_and_published: tuple[
        LanguageServer, asyncio.Queue[types.PublishDiagnosticsParams]
    ],
) -> None:
    server, published = server_and_published
    open_document(server, "qiime \\\nunknown")
    result = await asyncio.wait_for(published.get(), timeout=1)
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].range == types.Range(
        start=types.Position(1, 0),
        end=types.Position(1, 7),
    )
