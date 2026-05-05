from __future__ import annotations

from q2lsp.qiime.catalog import QiimeCatalog, make_catalog_provider
from q2lsp.qiime.types import CommandHierarchy


def test_catalog_provider_builds_catalog_once() -> None:
    hierarchy_calls = 0
    hierarchy: CommandHierarchy = {
        "qiime": {
            "builtins": ["info"],
            "info": {"type": "builtin", "short_help": "Display information"},
            "feature-table": {"description": "Feature table operations"},
        }
    }

    def get_hierarchy() -> CommandHierarchy:
        nonlocal hierarchy_calls
        hierarchy_calls += 1
        return hierarchy

    provider = make_catalog_provider(get_hierarchy)

    assert hierarchy_calls == 0

    catalog_1 = provider()
    catalog_2 = provider()

    assert hierarchy_calls == 1
    assert catalog_1 is catalog_2
    assert isinstance(catalog_1, QiimeCatalog)
    assert catalog_1.root_name == "qiime"
    assert catalog_1.builtin_names == ("info",)
    assert catalog_1.command_names == ("info", "feature-table")
    assert catalog_1.is_builtin("info") is True
