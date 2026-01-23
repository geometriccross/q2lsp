"""Test-only server entry point with stub hierarchy.

This is used by E2E tests to spawn a lightweight LSP server
without loading the full QIIME2 command hierarchy.
"""

from __future__ import annotations

from q2lsp.lsp.server import create_server
from q2lsp.qiime.types import CommandHierarchy


def _stub_hierarchy() -> CommandHierarchy:
    """Return a minimal stub hierarchy for testing."""
    return {
        "qiime": {
            "builtins": ["info", "tools"],
            "plugins": {
                "feature-table": {
                    "actions": {
                        "summarize": {
                            "signature": {
                                "inputs": {"table": "FeatureTable"},
                                "parameters": {"sample_metadata": "Metadata"},
                                "outputs": {"visualization": "Visualization"},
                            }
                        }
                    }
                }
            },
        }
    }


def _stub_hierarchy_provider() -> CommandHierarchy:
    """Stub hierarchy provider function."""
    return _stub_hierarchy()


def main() -> None:
    """Start the test LSP server."""
    server = create_server(get_hierarchy=_stub_hierarchy_provider)
    server.start_io()


if __name__ == "__main__":
    main()
