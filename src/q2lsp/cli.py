"""Command-line interface for q2lsp."""

from __future__ import annotations

import argparse
import dataclasses
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from q2lsp.logging import configure_logging, get_logger
from q2lsp.lsp.server import create_server
from q2lsp.qiime.hierarchy_provider import default_hierarchy_provider
from q2lsp.qiime.q2cli_gateway import create_qiime_help_provider


@dataclasses.dataclass(frozen=True)
class CliArgs:
    """Parsed command-line arguments."""

    transport: Literal["stdio", "tcp"]
    host: str
    port: int
    log_level: str
    log_file: Path | None
    debug: bool


def parse_args(argv: Sequence[str] | None = None) -> CliArgs:
    """
    Parse command-line arguments.

    Args:
        argv: Command-line arguments. If None, uses sys.argv[1:].

    Returns:
        Parsed arguments as CliArgs dataclass.
    """
    parser = argparse.ArgumentParser(
        prog="q2lsp",
        description="QIIME2 Language Server Protocol server",
    )

    parser.add_argument(
        "--transport",
        choices=["stdio", "tcp"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for TCP transport (default: 127.0.0.1)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=4389,
        help="Port for TCP transport (default: 4389)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Log level (default: INFO, or DEBUG if --debug is set)",
    )

    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Log file path (default: stderr)",
    )

    parser.add_argument(
        "-v",
        "--debug",
        action="store_true",
        help="Enable debug mode (sets log level to DEBUG unless --log-level is specified)",
    )

    args = parser.parse_args(argv)

    # Determine log level: explicit --log-level wins, otherwise --debug sets DEBUG
    if args.log_level is not None:
        log_level = args.log_level
    elif args.debug:
        log_level = "DEBUG"
    else:
        log_level = "INFO"

    return CliArgs(
        transport=args.transport,
        host=args.host,
        port=args.port,
        log_level=log_level,
        log_file=args.log_file,
        debug=args.debug,
    )


def run(argv: Sequence[str] | None = None) -> int:
    """
    Run the LSP server.

    Args:
        argv: Command-line arguments. If None, uses sys.argv[1:].

    Returns:
        Exit code (0 for success, 1 for error).
    """
    args = parse_args(argv)

    # Configure logging
    configure_logging(level=args.log_level, log_file=args.log_file)
    logger = get_logger("main")

    logger.info("Starting q2lsp server")
    logger.debug("Configuration: %s", args)

    try:
        # Build hierarchy provider
        get_hierarchy = default_hierarchy_provider()

        # Build help provider
        get_help = create_qiime_help_provider(max_content_width=80, color=False)

        # Create server
        server = create_server(
            get_hierarchy=get_hierarchy,
            get_help=get_help,
        )

        # Start appropriate transport
        if args.transport == "stdio":
            logger.info("Starting in stdio mode")
            server.start_io()
        else:
            logger.info("Starting in TCP mode on %s:%d", args.host, args.port)
            server.start_tcp(args.host, args.port)

        return 0

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        return 0

    except Exception:
        logger.critical("Fatal error in server", exc_info=True)
        return 1
