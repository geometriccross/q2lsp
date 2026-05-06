"""Tests for command-line interface."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from q2lsp.cli import CliArgs, parse_args, run


class TestParseArgs:
    """Tests for parse_args function."""

    def test_default_args(self) -> None:
        """Default arguments use stdio transport."""
        args = parse_args([])
        assert args.transport == "stdio"
        assert args.host == "127.0.0.1"
        assert args.port == 4389
        assert args.log_level == "INFO"
        assert args.log_file is None
        assert args.debug is False

    def test_tcp_transport(self) -> None:
        """Can specify TCP transport."""
        args = parse_args(["--transport", "tcp"])
        assert args.transport == "tcp"

    def test_custom_host_port(self) -> None:
        """Can specify custom host and port."""
        args = parse_args(["--transport", "tcp", "--host", "0.0.0.0", "--port", "9999"])
        assert args.host == "0.0.0.0"
        assert args.port == 9999

    def test_debug_flag_sets_debug_level(self) -> None:
        """--debug flag sets log level to DEBUG."""
        args = parse_args(["--debug"])
        assert args.debug is True
        assert args.log_level == "DEBUG"

    def test_debug_short_flag(self) -> None:
        """-v flag sets debug mode."""
        args = parse_args(["-v"])
        assert args.debug is True
        assert args.log_level == "DEBUG"

    def test_explicit_log_level_overrides_debug(self) -> None:
        """--log-level takes precedence over --debug."""
        args = parse_args(["--debug", "--log-level", "WARNING"])
        assert args.debug is True
        assert args.log_level == "WARNING"

    def test_log_file(self, tmp_path: Path) -> None:
        """Can specify log file path."""
        log_file = tmp_path / "test.log"
        args = parse_args(["--log-file", str(log_file)])
        assert args.log_file == log_file

    def test_invalid_transport_exits(self) -> None:
        """Invalid transport value exits with argparse usage error."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--transport", "invalid"])
        assert exc_info.value.code == 2

    def test_invalid_port_exits_with_useful_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Invalid port value exits with argparse usage error."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--port", "not_a_number"])
        assert exc_info.value.code == 2
        assert "invalid int value" in capsys.readouterr().err

    def test_invalid_log_level_exits(self) -> None:
        """Invalid log level exits with argparse usage error."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--log-level", "INVALID"])
        assert exc_info.value.code == 2

    def test_help_exits_zero_with_key_options(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--help exits successfully and documents key options."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--help"])
        assert exc_info.value.code == 0
        stdout = capsys.readouterr().out
        assert "--transport" in stdout
        assert "--host" in stdout
        assert "--port" in stdout
        assert "--log-level" in stdout
        assert "--log-file" in stdout
        assert "--debug" in stdout


class TestCliArgs:
    """Tests for CliArgs dataclass."""

    def test_is_frozen(self) -> None:
        """CliArgs is immutable."""
        args = CliArgs(
            transport="stdio",
            host="127.0.0.1",
            port=4389,
            log_level="INFO",
            log_file=None,
            debug=False,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            args.transport = "tcp"  # type: ignore[misc]


class FakeServer:
    """Server test double recording transport starts."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def start_io(self) -> None:
        self.calls.append(("start_io", None))

    def start_tcp(self, host: str, port: int) -> None:
        self.calls.append(("start_tcp", host, port))


@pytest.fixture
def fake_server_run(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeServer, list[tuple[str, Path | None]]]:
    """Patch server dependencies so run() never starts real transports."""
    import q2lsp.cli as cli

    server = FakeServer()
    logging_calls: list[tuple[str, Path | None]] = []

    monkeypatch.setattr(cli, "default_hierarchy_provider", lambda: object())
    monkeypatch.setattr(cli, "create_qiime_help_provider", lambda **_kwargs: object())
    monkeypatch.setattr(cli, "create_server", lambda **_kwargs: server)
    monkeypatch.setattr(
        cli,
        "configure_logging",
        lambda *, level, log_file: logging_calls.append((level, log_file)),
    )

    return server, logging_calls


class TestRun:
    """Tests for run orchestration."""

    def test_stdio_transport_starts_io(
        self,
        fake_server_run: tuple[FakeServer, list[tuple[str, Path | None]]],
    ) -> None:
        """stdio transport calls start_io."""
        server, _logging_calls = fake_server_run

        assert run([]) == 0

        assert server.calls == [("start_io", None)]

    def test_tcp_transport_starts_tcp(
        self,
        fake_server_run: tuple[FakeServer, list[tuple[str, Path | None]]],
    ) -> None:
        """TCP transport calls start_tcp with parsed host and port."""
        server, _logging_calls = fake_server_run

        assert run(["--transport", "tcp", "--host", "0.0.0.0", "--port", "9999"]) == 0

        assert server.calls == [("start_tcp", "0.0.0.0", 9999)]

    def test_keyboard_interrupt_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """KeyboardInterrupt is treated as clean shutdown."""
        import q2lsp.cli as cli

        monkeypatch.setattr(cli, "default_hierarchy_provider", lambda: (_ for _ in ()).throw(KeyboardInterrupt))

        assert run([]) == 0

    def test_generic_exception_returns_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unexpected exceptions return failure."""
        import q2lsp.cli as cli

        monkeypatch.setattr(cli, "default_hierarchy_provider", lambda: (_ for _ in ()).throw(RuntimeError))

        assert run([]) == 1

    def test_configures_logging_with_parsed_args(
        self,
        tmp_path: Path,
        fake_server_run: tuple[FakeServer, list[tuple[str, Path | None]]],
    ) -> None:
        """run() configures logging from parsed CLI arguments."""
        _server, logging_calls = fake_server_run
        log_file = tmp_path / "q2lsp.log"

        assert run(["--log-level", "WARNING", "--log-file", str(log_file)]) == 0

        assert logging_calls == [("WARNING", log_file)]
