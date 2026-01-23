"""Tests for command-line interface."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from q2lsp.cli import CliArgs, parse_args


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
        """Invalid transport value causes exit."""
        with pytest.raises(SystemExit):
            parse_args(["--transport", "invalid"])

    def test_invalid_port_exits(self) -> None:
        """Invalid port value causes exit."""
        with pytest.raises(SystemExit):
            parse_args(["--port", "not_a_number"])

    def test_invalid_log_level_exits(self) -> None:
        """Invalid log level causes exit."""
        with pytest.raises(SystemExit):
            parse_args(["--log-level", "INVALID"])


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
