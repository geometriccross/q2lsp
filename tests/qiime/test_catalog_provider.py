from __future__ import annotations

import pytest

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
    assert catalog_1.root().name == "qiime"
    assert [command.name for command in catalog_1.commands()] == [
        "info",
        "feature-table",
    ]
    assert catalog_1.command("info") is not None
    assert catalog_1.command("info").kind == "builtin"  # type: ignore[union-attr]


def test_catalog_provider_retries_failed_discovery() -> None:
    calls = 0

    def get_hierarchy() -> CommandHierarchy:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary discovery failure")
        return {"qiime": {}}

    provider = make_catalog_provider(get_hierarchy)
    with pytest.raises(RuntimeError, match="temporary discovery failure"):
        provider()

    catalog = provider()
    assert catalog.root().name == "qiime"
    assert provider() is catalog
    assert calls == 2
