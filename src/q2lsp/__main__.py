"""Entry point for QIIME2 LSP server."""

import sys

from q2lsp.cli import run


def main() -> None:
    """Start the LSP server."""
    sys.exit(run())


if __name__ == "__main__":
    main()
