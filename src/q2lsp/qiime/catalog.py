from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeAlias, cast

from q2lsp.qiime.hierarchy_keys import (
    BUILTIN_NODE_METADATA_KEYS,
    COMMAND_METADATA_KEYS,
    ROOT_METADATA_KEYS,
)
from q2lsp.qiime.types import CommandHierarchy, JsonObject, JsonPrimitive, JsonValue

CatalogProvider: TypeAlias = Callable[[], "QiimeCatalog"]

FrozenJsonValue: TypeAlias = (
    JsonPrimitive | tuple["FrozenJsonValue", ...] | Mapping[str, "FrozenJsonValue"]
)
FrozenJsonObject: TypeAlias = Mapping[str, FrozenJsonValue]


@dataclass(frozen=True)
class QiimeCatalog:
    """Owned catalog abstraction for QIIME command metadata.

    This is intentionally minimal for the architecture foundation phase: it
    wraps the existing command hierarchy shape without exposing q2cli/click
    implementation types to callers.
    """

    hierarchy: Mapping[str, FrozenJsonObject]

    @classmethod
    def from_hierarchy(cls, hierarchy: CommandHierarchy) -> "QiimeCatalog":
        return cls(hierarchy=_freeze_hierarchy(hierarchy))

    @property
    def root_name(self) -> str:
        return next(iter(self.hierarchy), "qiime")

    @property
    def builtin_names(self) -> tuple[str, ...]:
        root_node = self._root_node()
        if root_node is None:
            return ()
        builtins = root_node.get("builtins", ())
        if not isinstance(builtins, tuple):
            return ()
        return tuple(name for name in builtins if isinstance(name, str))

    @property
    def command_names(self) -> tuple[str, ...]:
        root_node = self._root_node()
        if root_node is None:
            return ()

        builtins = self.builtin_names
        builtin_set = set(builtins)
        plugins = tuple(
            name
            for name, value in root_node.items()
            if name not in {"builtins", *builtin_set} and isinstance(value, Mapping)
        )
        return (*builtins, *plugins)

    def is_builtin(self, command_name: str) -> bool:
        return command_name in self.builtin_names

    def valid_plugins_and_builtins(self) -> tuple[set[str], set[str]]:
        root_node = self._root_node()
        if root_node is None:
            return set(), set()

        valid_builtins = set(self.builtin_names)
        valid_plugins = {
            key
            for key, value in root_node.items()
            if key not in ROOT_METADATA_KEYS
            and key not in valid_builtins
            and isinstance(value, Mapping)
        }
        return valid_plugins, valid_builtins

    def valid_actions(self, command_name: str) -> list[str]:
        command_node = self._command_node(command_name)
        if command_node is None:
            return []

        return [
            key
            for key, value in command_node.items()
            if key not in COMMAND_METADATA_KEYS and isinstance(value, Mapping)
        ]

    def is_builtin_leaf(self, command_name: str) -> bool:
        command_node = self._command_node(command_name)
        if command_node is None or command_node.get("type") != "builtin":
            return False

        return not any(
            key not in BUILTIN_NODE_METADATA_KEYS and isinstance(value, Mapping)
            for key, value in command_node.items()
        )

    def command_node(self, command_name: str) -> dict[str, JsonValue] | None:
        value = self._command_node(command_name)
        if value is None:
            return None
        return cast(dict[str, JsonValue], _thaw_json(value))

    def root_node(self) -> JsonObject | None:
        root_node = self._root_node()
        if root_node is None:
            return None
        return cast(JsonObject, _thaw_json(root_node))

    def action_node(self, command_name: str, action_name: str) -> JsonObject | None:
        command_node = self.command_node(command_name)
        if command_node is None:
            return None
        value = command_node.get(action_name)
        if not isinstance(value, dict):
            return None
        return value

    def root_help(self) -> str | None:
        root_node = self._root_node()
        if root_node is None:
            return None
        return _string_value(root_node, "help") or _string_value(
            root_node, "short_help"
        )

    def command_help(self, command_name: str) -> str | None:
        root_node = self._root_node()
        if root_node is None:
            return None
        command_node = root_node.get(command_name)
        if not isinstance(command_node, Mapping):
            return None
        return (
            _string_value(command_node, "help")
            or _string_value(command_node, "short_help")
            or _string_value(command_node, "short_description")
            or _string_value(command_node, "description")
        )

    def action_help(self, command_name: str, action_name: str) -> str | None:
        root_node = self._root_node()
        if root_node is None:
            return None
        command_node = root_node.get(command_name)
        if not isinstance(command_node, Mapping):
            return None
        action_node = command_node.get(action_name)
        if not isinstance(action_node, Mapping):
            return None

        description = _string_value(action_node, "description")
        if description is None:
            return None

        epilog = action_node.get("epilog")
        if not isinstance(epilog, tuple) or not epilog:
            return description

        epilog_text = "\n".join(str(line) for line in epilog)
        if not epilog_text:
            return description
        return f"{description}\n\n{epilog_text}"

    def _root_node(self) -> FrozenJsonObject | None:
        root_node = self.hierarchy.get(self.root_name)
        if root_node is None:
            return None
        return root_node

    def _command_node(self, command_name: str) -> FrozenJsonObject | None:
        root_node = self._root_node()
        if root_node is None:
            return None
        value = root_node.get(command_name)
        if not isinstance(value, Mapping):
            return None
        return value


def make_catalog_provider(get_hierarchy: Callable[[], CommandHierarchy]) -> CatalogProvider:
    catalog: QiimeCatalog | None = None

    def provider() -> QiimeCatalog:
        nonlocal catalog
        if catalog is None:
            catalog = QiimeCatalog.from_hierarchy(get_hierarchy())
        return catalog

    return provider


def _freeze_json(value: JsonValue) -> FrozenJsonValue:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _freeze_hierarchy(hierarchy: CommandHierarchy) -> Mapping[str, FrozenJsonObject]:
    return MappingProxyType(
        {
            command_name: MappingProxyType(
                {key: _freeze_json(item) for key, item in command.items()}
            )
            for command_name, command in hierarchy.items()
        }
    )


def _thaw_json(value: FrozenJsonValue) -> JsonValue:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _string_value(node: Mapping[str, FrozenJsonValue], key: str) -> str | None:
    value = node.get(key)
    if not isinstance(value, str) or not value:
        return None
    return value
