from __future__ import annotations

import pytest

from q2lsp.qiime.catalog import QiimeCatalog
from q2lsp.qiime.catalog_facts import (
    QiimeActionFact,
    QiimeCommandFact,
    QiimeOptionFact,
    QiimeRootFact,
)
from q2lsp.qiime.types import CommandHierarchy


def test_qiime_catalog_wraps_hierarchy_immutably() -> None:
    hierarchy: CommandHierarchy = {
        "qiime": {
            "name": "qiime",
            "short_help": "QIIME summary",
            "builtins": ["info"],
            "info": {"short_help": "Display information", "type": "builtin"},
        }
    }

    catalog = QiimeCatalog.from_hierarchy(hierarchy)

    hierarchy["other"] = {"builtins": []}
    hierarchy["qiime"]["builtins"] = ["changed"]
    hierarchy["qiime"]["info"] = {"short_help": "Changed", "type": "builtin"}

    assert catalog.root() == QiimeRootFact(
        name="qiime", summary="QIIME summary", help_text="QIIME summary"
    )
    assert [command.name for command in catalog.commands()] == ["info"]
    assert catalog.command("info") == QiimeCommandFact(
        name="info",
        kind="builtin",
        summary="Display information",
        help_text="Display information",
        has_actions=False,
    )


def test_qiime_catalog_rejects_malformed_hierarchy_without_qiime_root() -> None:
    with pytest.raises(ValueError, match="QIIME root command"):
        QiimeCatalog.from_hierarchy({})


def test_qiime_catalog_returns_root_fact() -> None:
    hierarchy: CommandHierarchy = {
        "qiime": {
            "name": "qiime",
            "help": "Root help",
            "short_help": "Root summary",
            "builtins": [],
        }
    }

    catalog = QiimeCatalog.from_hierarchy(hierarchy)

    assert catalog.root() == QiimeRootFact(
        name="qiime", summary="Root summary", help_text="Root help"
    )


def test_qiime_catalog_returns_command_facts_for_builtins_and_plugins() -> None:
    hierarchy: CommandHierarchy = {
        "qiime": {
            "builtins": ["info", "tools"],
            "info": {
                "type": "builtin",
                "short_help": "Display information",
            },
            "tools": {
                "type": "builtin",
                "short_help": "Tools",
                "import": {"description": "Import data"},
            },
            "feature-table": {
                "short_description": "Feature table operations",
                "summarize": {"description": "Summarize feature table"},
            },
            "metadata": "not a command node",
        }
    }

    catalog = QiimeCatalog.from_hierarchy(hierarchy)

    assert catalog.commands() == (
        QiimeCommandFact(
            name="info",
            kind="builtin",
            summary="Display information",
            help_text="Display information",
            has_actions=False,
        ),
        QiimeCommandFact(
            name="tools",
            kind="builtin",
            summary="Tools",
            help_text="Tools",
            has_actions=True,
        ),
        QiimeCommandFact(
            name="feature-table",
            kind="plugin",
            summary="Feature table operations",
            help_text="Feature table operations",
            has_actions=True,
        ),
    )
    assert catalog.command("missing") is None


def test_qiime_catalog_returns_action_facts_for_plugins_and_builtin_groups() -> None:
    hierarchy: CommandHierarchy = {
        "qiime": {
            "builtins": ["tools"],
            "tools": {
                "type": "builtin",
                "import": {"description": "Import data"},
            },
            "feature-table": {
                "name": "feature-table",
                "description": "Feature table operations",
                "actions": {},
                "summarize": {
                    "description": "Summarize feature table",
                    "epilog": ["Example command"],
                },
                "metadata": "not an action node",
            },
        }
    }

    catalog = QiimeCatalog.from_hierarchy(hierarchy)

    assert catalog.actions("tools") == (
        QiimeActionFact(
            command_name="tools",
            name="import",
            summary="Import data",
            help_text="Import data",
        ),
    )
    assert catalog.actions("feature-table") == (
        QiimeActionFact(
            command_name="feature-table",
            name="summarize",
            summary="Summarize feature table",
            help_text="Summarize feature table\n\nExample command",
        ),
    )
    assert catalog.action("feature-table", "missing") is None
    assert catalog.actions("missing") == ()


def test_qiime_catalog_returns_option_facts_from_action_signature() -> None:
    hierarchy: CommandHierarchy = {
        "qiime": {
            "builtins": [],
            "feature-table": {
                "summarize": {
                    "description": "Summarize feature table",
                    "signature": [
                        {
                            "name": "table",
                            "type": "FeatureTable",
                            "description": "Input table",
                            "signature_type": "input",
                        },
                        {
                            "name": "sampling_depth",
                            "type": "Int",
                            "description": "Reads per sample",
                            "signature_type": "parameter",
                            "default": 1000,
                        },
                        {
                            "name": "metadata_file",
                            "type": "Metadata",
                            "description": "Sample metadata",
                            "signature_type": "metadata",
                            "is_bool_flag": True,
                        },
                    ],
                }
            },
        }
    }

    catalog = QiimeCatalog.from_hierarchy(hierarchy)

    assert catalog.action_options("feature-table", "summarize") == (
        QiimeOptionFact(
            name="table",
            label="--i-table",
            kind="input",
            required=True,
            description="Input table",
            value_type="FeatureTable",
        ),
        QiimeOptionFact(
            name="sampling_depth",
            label="--p-sampling-depth",
            kind="parameter",
            required=False,
            description="Reads per sample",
            value_type="Int",
        ),
        QiimeOptionFact(
            name="metadata_file",
            label="--m-metadata-file",
            kind="metadata",
            required=True,
            description="Sample metadata",
            value_type="Metadata",
            is_bool_flag=True,
        ),
    )
    assert catalog.action_options("feature-table", "missing") == ()


def test_qiime_catalog_action_help_uses_description_and_epilog_only() -> None:
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

    assert catalog.root().help_text == "Root short help"
    assert catalog.command("info") is not None
    assert catalog.command("info").help_text == "Info help"  # type: ignore[union-attr]
    assert catalog.command("tools") is not None
    assert catalog.command("tools").help_text == "Tools description"  # type: ignore[union-attr]
    assert catalog.action("feature-table", "summarize") is not None
    assert catalog.action("feature-table", "summarize").help_text == ""  # type: ignore[union-attr]
    assert catalog.action("feature-table", "tabulate") is not None
    assert (
        catalog.action("feature-table", "tabulate").help_text == "Tabulate description"
    )  # type: ignore[union-attr]
