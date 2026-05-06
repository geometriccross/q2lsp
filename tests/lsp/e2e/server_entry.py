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
            "info": {
                "name": "info",
                "type": "builtin",
                "short_help": "Show QIIME 2 information.",
            },
            "tools": {
                "name": "tools",
                "type": "builtin",
                "short_help": "Access QIIME 2 tools.",
            },
            "feature-table": {
                "id": "feature-table",
                "name": "feature-table",
                "short_description": "Work with feature tables.",
                "summarize": {
                    "description": "Summarize a feature table.",
                    "signature": [
                        {
                            "name": "table",
                            "type": "FeatureTable",
                            "description": "Feature table to summarize.",
                            "signature_type": "input",
                            "required": True,
                        },
                        {
                            "name": "sample_metadata",
                            "type": "Metadata",
                            "description": "Sample metadata to summarize by.",
                            "signature_type": "parameter",
                        },
                        {
                            "name": "visualization",
                            "type": "Visualization",
                            "description": "Output visualization.",
                            "signature_type": "output",
                            "required": True,
                        },
                    ],
                },
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
