"""Gateway conversion and help rendering using real Click commands."""

from __future__ import annotations

from typing import cast

import click
import pytest

from q2lsp.qiime.q2cli_gateway import build_qiime_hierarchy, create_qiime_help_provider
from q2lsp.qiime.types import JsonObject


def test_build_hierarchy_exposes_click_option_signature_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action = click.Command(
        "inspect",
        params=[
            click.Option(["--hidden-token"], hidden=True),
            click.Option(["--input-path"], required=True, help="Input path."),
            click.Option(["--threads"], default=4, help="Thread count."),
            click.Option(["--verbose/--no-verbose"], default=False),
        ],
    )
    tools = click.Group("tools", commands={"inspect": action})
    root = click.Group("qiime", commands={"tools": tools})
    monkeypatch.setattr(root, "_builtin_commands", {"tools": tools}, raising=False)
    monkeypatch.setattr(root, "_plugin_lookup", {}, raising=False)
    monkeypatch.setattr("q2lsp.qiime.q2cli_gateway._RootCommand", lambda: root)

    hierarchy = build_qiime_hierarchy()
    tools_entry = cast(JsonObject, hierarchy["qiime"]["tools"])
    inspect_entry = cast(JsonObject, tools_entry["inspect"])
    signature = cast(list[JsonObject], inspect_entry["signature"])

    assert [param["name"] for param in signature] == [
        "input_path",
        "threads",
        "verbose",
    ]
    params = {param["name"]: param for param in signature}
    assert params["input_path"]["required"] is True
    assert "default" not in params["input_path"]
    assert params["threads"]["default"] == 4
    assert params["verbose"]["default"] is False
    assert params["verbose"]["is_bool_flag"] is True


@pytest.fixture
def root_command(monkeypatch: pytest.MonkeyPatch) -> click.Group:
    tools = click.Group("tools", help="QIIME 2 tools")
    tools.add_command(click.Command("export", help="Export data"))
    root = click.Group("qiime", help="QIIME 2 CLI")
    root.add_command(click.Command("info", help="Display deployment information"))
    root.add_command(tools)
    monkeypatch.setattr("q2lsp.qiime.q2cli_gateway._get_root_command", lambda: root)
    return root


@pytest.mark.parametrize(
    ("path", "usage", "description"),
    [
        ([], "Usage: qiime [OPTIONS] COMMAND [ARGS]...", "QIIME 2 CLI"),
        (["info"], "Usage: qiime info [OPTIONS]", "Display deployment information"),
        (["tools"], "Usage: qiime tools [OPTIONS] COMMAND [ARGS]...", "QIIME 2 tools"),
        (["tools", "export"], "Usage: qiime tools export [OPTIONS]", "Export data"),
    ],
)
def test_provider_renders_help_with_full_command_path(
    root_command: click.Group,
    path: list[str],
    usage: str,
    description: str,
) -> None:
    help_text = create_qiime_help_provider()(path)
    assert help_text is not None
    assert usage in help_text
    assert description in help_text
    assert "--help" in help_text


@pytest.mark.parametrize("path", [["missing"], ["tools", "missing"], ["info", "extra"]])
def test_provider_rejects_invalid_command_paths(
    root_command: click.Group, path: list[str]
) -> None:
    assert create_qiime_help_provider()(path) is None


def test_provider_passes_help_formatting_settings(
    root_command: click.Group,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contexts: list[click.Context] = []
    render_help = root_command.get_help

    def capture_context(ctx: click.Context) -> str:
        contexts.append(ctx)
        return render_help(ctx)

    monkeypatch.setattr(root_command, "get_help", capture_context)
    help_text = create_qiime_help_provider(max_content_width=120, color=True)([])

    assert help_text is not None
    assert "Usage: qiime" in help_text
    assert contexts[0].max_content_width == 120
    assert contexts[0].color is True


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("\x1b[31mUsage:\x1b[0m qiime [OPTIONS]\n", "Usage: qiime [OPTIONS]\n"),
        (
            "\x1b[?25l\x1b[2JUsage:\x1b[1A qiime [OPTIONS]\x1b[?25h\n",
            "Usage: qiime [OPTIONS]\n",
        ),
        ("Usage:\b qiime [OPTIONS]\r\n\x00\x07", "Usage: qiime [OPTIONS]\n"),
        ("Usage:\n\tqiime [OPTIONS]\n\x00", "Usage:\n\tqiime [OPTIONS]\n"),
    ],
)
def test_provider_sanitizes_external_help_text(
    root_command: click.Group,
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
    expected: str,
) -> None:
    monkeypatch.setattr(root_command, "get_help", lambda _ctx: raw)
    assert create_qiime_help_provider()([]) == expected
