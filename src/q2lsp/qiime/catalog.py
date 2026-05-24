from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeAlias, cast

from q2lsp.qiime.catalog_facts import (
    QiimeActionFact,
    QiimeCommandFact,
    QiimeOptionFact,
    QiimeOptionKind,
    QiimeRootFact,
)
from q2lsp.qiime.hierarchy_keys import (
    BUILTIN_NODE_METADATA_KEYS,
    COMMAND_METADATA_KEYS,
    ROOT_METADATA_KEYS,
)
from q2lsp.qiime.options import (
    format_qiime_option_label,
    param_is_required,
)
from q2lsp.qiime.signature_params import iter_signature_params
from q2lsp.qiime.types import CommandHierarchy, JsonObject, JsonPrimitive, JsonValue

CatalogProvider: TypeAlias = Callable[[], "QiimeCatalog"]

_ROOT_NAME = "qiime"

FrozenJsonValue: TypeAlias = (
    JsonPrimitive | tuple["FrozenJsonValue", ...] | Mapping[str, "FrozenJsonValue"]
)
FrozenJsonObject: TypeAlias = Mapping[str, FrozenJsonValue]


@dataclass(frozen=True)
class QiimeCatalog:
    """Owned catalog abstraction for QIIME command facts."""

    _hierarchy: Mapping[str, FrozenJsonObject]

    @classmethod
    def from_hierarchy(cls, hierarchy: CommandHierarchy) -> "QiimeCatalog":
        if _ROOT_NAME not in hierarchy:
            raise ValueError("Malformed command hierarchy: missing QIIME root command")
        return cls(_hierarchy=_freeze_hierarchy(hierarchy))

    def root(self) -> QiimeRootFact:
        root_node = self._root_node()
        return QiimeRootFact(
            name=_string_value(root_node, "name") or _ROOT_NAME,
            summary=_string_value(root_node, "short_help"),
            help_text=(
                _string_value(root_node, "help")
                or _string_value(root_node, "short_help")
            ),
        )

    def commands(self) -> tuple[QiimeCommandFact, ...]:
        root_node = self._root_node()
        builtins = _builtin_names(root_node)
        builtin_set = set(builtins)
        plugin_names = tuple(
            name
            for name, value in root_node.items()
            if name not in ROOT_METADATA_KEYS
            and name not in builtin_set
            and isinstance(value, Mapping)
        )
        return tuple(
            command
            for command_name in (*builtins, *plugin_names)
            if (command := self.command(command_name)) is not None
        )

    def command(self, name: str) -> QiimeCommandFact | None:
        root_node = self._root_node()
        command_node = self._command_node(name)
        if command_node is None:
            return None

        builtins = _builtin_names(root_node)
        is_builtin = name in builtins
        return QiimeCommandFact(
            name=name,
            kind="builtin" if is_builtin else "plugin",
            summary=_command_summary(command_node, is_builtin=is_builtin),
            help_text=_command_help_text(command_node),
            has_actions=_has_action_nodes(command_node, is_builtin=is_builtin),
        )

    def actions(self, command_name: str) -> tuple[QiimeActionFact, ...]:
        command_node = self._command_node(command_name)
        if command_node is None:
            return ()

        return tuple(
            self._action_from_node(command_name, action_name, action_node)
            for action_name, action_node in command_node.items()
            if action_name not in COMMAND_METADATA_KEYS
            and isinstance(action_node, Mapping)
        )

    def action(self, command_name: str, action_name: str) -> QiimeActionFact | None:
        action_node = self._action_node(command_name, action_name)
        if action_node is None:
            return None
        return self._action_from_node(command_name, action_name, action_node)

    def action_options(
        self, command_name: str, action_name: str
    ) -> tuple[QiimeOptionFact, ...]:
        action_node = self._action_node(command_name, action_name)
        if action_node is None:
            return ()

        thawed_action = cast(JsonObject, _thaw_json(action_node))
        options: list[QiimeOptionFact] = []
        for name, option_prefix, param in iter_signature_params(thawed_action):
            options.append(
                QiimeOptionFact(
                    name=name,
                    label=format_qiime_option_label(option_prefix, name),
                    kind=_option_kind(option_prefix),
                    required=param_is_required(param),
                    description=_param_text(param, "description"),
                    value_type=_param_text(param, "type"),
                    is_bool_flag=param.get("is_bool_flag") is True,
                )
            )
        return tuple(options)

    def _root_node(self) -> FrozenJsonObject:
        return self._hierarchy[_ROOT_NAME]

    def _command_node(self, command_name: str) -> FrozenJsonObject | None:
        value = self._root_node().get(command_name)
        if not isinstance(value, Mapping):
            return None
        return value

    def _action_node(
        self, command_name: str, action_name: str
    ) -> FrozenJsonObject | None:
        command_node = self._command_node(command_name)
        if command_node is None:
            return None
        value = command_node.get(action_name)
        if not isinstance(value, Mapping):
            return None
        return value

    def _action_from_node(
        self,
        command_name: str,
        action_name: str,
        action_node: FrozenJsonObject,
    ) -> QiimeActionFact:
        return QiimeActionFact(
            command_name=command_name,
            name=action_name,
            summary=_action_summary(action_node),
            help_text=_action_help_text(action_node),
        )


def make_catalog_provider(
    get_hierarchy: Callable[[], CommandHierarchy],
) -> CatalogProvider:
    catalog: QiimeCatalog | None = None

    def provider() -> QiimeCatalog:
        nonlocal catalog
        if catalog is None:
            catalog = QiimeCatalog.from_hierarchy(get_hierarchy())
        return catalog

    return provider


def _builtin_names(root_node: FrozenJsonObject) -> tuple[str, ...]:
    builtins = root_node.get("builtins", ())
    if not isinstance(builtins, tuple):
        return ()
    return tuple(name for name in builtins if isinstance(name, str))


def _has_action_nodes(command_node: FrozenJsonObject, *, is_builtin: bool) -> bool:
    metadata_keys = BUILTIN_NODE_METADATA_KEYS if is_builtin else COMMAND_METADATA_KEYS
    return any(
        key not in metadata_keys and isinstance(value, Mapping)
        for key, value in command_node.items()
    )


def _command_summary(command_node: FrozenJsonObject, *, is_builtin: bool) -> str:
    if is_builtin:
        return _string_value(command_node, "short_help") or _string_value(
            command_node, "help"
        )
    return (
        _string_value(command_node, "short_description")
        or _string_value(command_node, "description")
        or _string_value(command_node, "short_help")
        or _string_value(command_node, "help")
    )


def _command_help_text(command_node: FrozenJsonObject) -> str:
    return (
        _string_value(command_node, "help")
        or _string_value(command_node, "short_help")
        or _string_value(command_node, "short_description")
        or _string_value(command_node, "description")
    )


def _action_summary(action_node: FrozenJsonObject) -> str:
    return (
        _string_value(action_node, "description")
        or _string_value(action_node, "short_description")
        or _string_value(action_node, "short_help")
        or _string_value(action_node, "help")
    )


def _action_help_text(action_node: FrozenJsonObject) -> str:
    description = _string_value(action_node, "description")
    if not description:
        return ""

    epilog = action_node.get("epilog")
    if not isinstance(epilog, tuple) or not epilog:
        return description

    epilog_text = "\n".join(str(line) for line in epilog)
    if not epilog_text:
        return description
    return f"{description}\n\n{epilog_text}"


def _option_kind(option_prefix: str) -> QiimeOptionKind:
    if option_prefix == "i":
        return "input"
    if option_prefix == "o":
        return "output"
    if option_prefix == "p":
        return "parameter"
    if option_prefix == "m":
        return "metadata"
    return "unknown"


def _param_text(param: Mapping[str, object], key: str) -> str:
    value = param.get(key)
    if not isinstance(value, str):
        return ""
    return value


def _freeze_json(value: JsonValue) -> FrozenJsonValue:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )
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


def _string_value(node: Mapping[str, FrozenJsonValue], key: str) -> str:
    value = node.get(key)
    if not isinstance(value, str) or not value:
        return ""
    return value
