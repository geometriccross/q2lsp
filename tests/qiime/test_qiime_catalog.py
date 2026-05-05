from __future__ import annotations

import pytest

from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.q2cli_gateway import build_qiime_catalog
from q2lsp.qiime.types import CommandHierarchy


def test_qiime_catalog_wraps_hierarchy_immutably() -> None:
    hierarchy: CommandHierarchy = {"qiime": {"builtins": []}}

    catalog = QiimeCatalog.from_hierarchy(hierarchy)

    hierarchy["other"] = {"builtins": []}


    assert catalog.root_name == "qiime"
    assert "other" not in catalog.hierarchy
    with pytest.raises(TypeError):
        catalog.hierarchy["new"] = {"builtins": []}  # type: ignore[index]


def test_qiime_catalog_deep_freezes_hierarchy() -> None:
    hierarchy: CommandHierarchy = {
        "qiime": {"builtins": ["info"], "plugin": {"actions": {"act": {}}}}
    }

    catalog = QiimeCatalog.from_hierarchy(hierarchy)
    hierarchy["qiime"]["builtins"] = ["changed"]
    plugin = hierarchy["qiime"]["plugin"]
    assert isinstance(plugin, dict)
    plugin["actions"] = {}

    qiime = catalog.hierarchy["qiime"]
    assert qiime["builtins"] == ("info",)
    assert isinstance(qiime["builtins"], tuple)
    with pytest.raises(AttributeError):
        qiime["builtins"].append("changed")  # type: ignore[attr-defined,union-attr]
    with pytest.raises(TypeError):
        qiime["plugin"]["actions"] = {}  # type: ignore[index]


def test_build_qiime_catalog_uses_owned_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    hierarchy: CommandHierarchy = {"qiime": {"builtins": []}}
    monkeypatch.setattr(
        "q2lsp.qiime.q2cli_gateway.build_qiime_hierarchy",
        lambda: hierarchy,
    )

    catalog = build_qiime_catalog()

    assert isinstance(catalog, QiimeCatalog)
    assert catalog.hierarchy["qiime"]["builtins"] == ()


def test_qiime_catalog_exposes_completion_accessors_without_mutable_leaks() -> None:
    hierarchy: CommandHierarchy = {
        "qiime": {
            "builtins": ["info"],
            "info": {"short_help": "Display information"},
            "feature-table": {
                "short_description": "Feature table operations",
                "summarize": {"description": "Summarize feature table"},
            },
        }
    }

    catalog = QiimeCatalog.from_hierarchy(hierarchy)
    info = catalog.command_node("info")
    assert info is not None
    info["short_help"] = "changed"

    assert catalog.builtin_names == ("info",)
    assert catalog.command_names == ("info", "feature-table")
    assert catalog.is_builtin("info") is True
    assert catalog.is_builtin("feature-table") is False
    assert catalog.command_node("info") == {"short_help": "Display information"}
    assert catalog.command_node("missing") is None


def test_qiime_catalog_root_node_returns_owned_thawed_copy() -> None:
    hierarchy: CommandHierarchy = {
        "qiime": {
            "builtins": ["info"],
            "feature-table": {"actions": {"summarize": {}}},
        }
    }
    catalog = QiimeCatalog.from_hierarchy(hierarchy)

    root = catalog.root_node()
    assert root is not None
    root["builtins"] = ["changed"]
    feature_table = root["feature-table"]
    assert isinstance(feature_table, dict)
    feature_table["actions"] = {}

    assert catalog.root_node() == {
        "builtins": ["info"],
        "feature-table": {"actions": {"summarize": {}}},
    }


def test_qiime_catalog_action_node_returns_owned_thawed_copy() -> None:
    hierarchy: CommandHierarchy = {
        "qiime": {
            "builtins": [],
            "feature-table": {
                "summarize": {"epilog": ["example"], "inputs": {"table": {}}}
            },
        }
    }
    catalog = QiimeCatalog.from_hierarchy(hierarchy)

    action = catalog.action_node("feature-table", "summarize")
    assert action is not None
    action["epilog"] = ["changed"]
    inputs = action["inputs"]
    assert isinstance(inputs, dict)
    inputs["table"] = {"changed": True}

    assert catalog.action_node("feature-table", "summarize") == {
        "epilog": ["example"],
        "inputs": {"table": {}},
    }


def test_qiime_catalog_accessors_handle_absent_root() -> None:
    catalog = QiimeCatalog.from_hierarchy({})

    assert catalog.root_node() is None
    assert catalog.command_node("info") is None
    assert catalog.action_node("feature-table", "summarize") is None
    assert catalog.builtin_names == ()
    assert catalog.command_names == ()
    assert catalog.valid_plugins_and_builtins() == (set(), set())
    assert catalog.valid_actions("feature-table") == []
    assert catalog.is_builtin("info") is False
    assert catalog.is_builtin_leaf("info") is False
    assert catalog.root_help() is None
    assert catalog.command_help("info") is None
    assert catalog.action_help("feature-table", "summarize") is None


def test_qiime_catalog_accessors_handle_empty_root() -> None:
    catalog = QiimeCatalog.from_hierarchy({"qiime": {}})

    assert catalog.root_node() == {}
    assert catalog.command_node("info") is None
    assert catalog.action_node("feature-table", "summarize") is None
    assert catalog.builtin_names == ()
    assert catalog.command_names == ()
    assert catalog.valid_plugins_and_builtins() == (set(), set())
    assert catalog.valid_actions("feature-table") == []


def test_qiime_catalog_returns_valid_plugins_and_builtins() -> None:
    hierarchy: CommandHierarchy = {
        "qiime": {
            "name": "qiime",
            "help": "Root help",
            "builtins": ["info"],
            "info": {"type": "builtin"},
            "feature-table": {"description": "Feature table operations"},
            "metadata": "not a command node",
        }
    }

    catalog = QiimeCatalog.from_hierarchy(hierarchy)

    assert catalog.valid_plugins_and_builtins() == ({"feature-table"}, {"info"})


def test_qiime_catalog_returns_valid_actions_for_command() -> None:
    hierarchy: CommandHierarchy = {
        "qiime": {
            "builtins": [],
            "feature-table": {
                "name": "feature-table",
                "description": "Feature table operations",
                "actions": {},
                "summarize": {"description": "Summarize feature table"},
                "metadata": "not an action node",
            },
        }
    }

    catalog = QiimeCatalog.from_hierarchy(hierarchy)

    assert catalog.valid_actions("feature-table") == ["summarize"]


def test_qiime_catalog_matches_builtin_leaf_semantics() -> None:
    hierarchy: CommandHierarchy = {
        "qiime": {
            "builtins": ["info", "tools"],
            "info": {
                "type": "builtin",
                "short_help": "Display information",
            },
            "tools": {
                "type": "builtin",
                "export": {"short_help": "Export data"},
            },
            "feature-table": {
                "summarize": {"description": "Summarize feature table"},
            },
        }
    }

    catalog = QiimeCatalog.from_hierarchy(hierarchy)

    assert catalog.is_builtin_leaf("info") is True
    assert catalog.is_builtin_leaf("tools") is False
    assert catalog.is_builtin_leaf("feature-table") is False


def test_qiime_catalog_exposes_hover_help_accessors() -> None:
    hierarchy: CommandHierarchy = {
        "qiime": {
            "help": "Root help",
            "short_help": "Root short help",
            "builtins": ["info"],
            "info": {"short_help": "Info short help"},
            "feature-table": {
                "short_description": "Feature table short description",
                "description": "Feature table description",
                "summarize": {
                    "description": "Summarize feature table",
                    "epilog": ["Example command"],
                },
            },
        }
    }

    catalog = QiimeCatalog.from_hierarchy(hierarchy)

    assert catalog.root_help() == "Root help"
    assert catalog.command_help("info") == "Info short help"
    assert catalog.command_help("feature-table") == "Feature table short description"
    assert catalog.action_help("feature-table", "summarize") == (
        "Summarize feature table\n\nExample command"
    )


def test_qiime_catalog_help_accessors_use_fallback_precedence() -> None:
    hierarchy: CommandHierarchy = {
        "qiime": {
            "short_help": "Root short help",
            "builtins": [],
            "info": {"help": "Info help", "short_help": "Info short help"},
            "tools": {"description": "Tools description"},
            "feature-table": {
                "description": "Feature table description",
                "summarize": {"short_description": "Summarize short description"},
                "tabulate": {
                    "description": "Tabulate description",
                    "epilog": [],
                },
            },
        }
    }
    catalog = QiimeCatalog.from_hierarchy(hierarchy)

    assert catalog.root_help() == "Root short help"
    assert catalog.command_help("info") == "Info help"
    assert catalog.command_help("tools") == "Tools description"
    assert catalog.command_help("feature-table") == "Feature table description"
    assert catalog.action_help("feature-table", "summarize") is None
    assert catalog.action_help("feature-table", "tabulate") == "Tabulate description"
