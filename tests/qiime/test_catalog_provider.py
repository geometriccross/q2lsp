from __future__ import annotations

from q2lsp.qiime.catalog import make_catalog_provider
from q2lsp.qiime.types import CommandHierarchy


def test_catalog_provider_builds_catalog_once() -> None:
    hierarchy_calls = 0
    hierarchy: CommandHierarchy = {"qiime": {"builtins": []}}

    def get_hierarchy() -> CommandHierarchy:
        nonlocal hierarchy_calls
        hierarchy_calls += 1
        return hierarchy

    provider = make_catalog_provider(get_hierarchy)

    catalog_1 = provider()
    catalog_2 = provider()

    assert hierarchy_calls == 1
    assert catalog_1 is catalog_2
