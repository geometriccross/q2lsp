"""Entry point for QIIME2 LSP server."""

from q2lsp.lsp.server import create_server
from q2lsp.qiime.hierarchy_provider import default_hierarchy_provider


def main() -> None:
    """Start the LSP server in stdio mode."""
    get_hierarchy = default_hierarchy_provider()
    server = create_server(get_hierarchy=get_hierarchy)
    server.start_io()


if __name__ == "__main__":
    main()
