from __future__ import annotations

from typing import TypedDict, TypeAlias

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
CommandHierarchy: TypeAlias = dict[str, JsonObject]


class ActionSignatureParameter(TypedDict, total=False):
    name: str
    type: str
    repr: str
    ast: dict[str, JsonValue]
    description: str
    default: JsonValue
    metavar: str
    multiple: str | None
    is_bool_flag: bool
    metadata: str | None


class ActionCommandProperties(TypedDict):
    id: str
    name: str
    type: str
    description: str
    signature: list[ActionSignatureParameter]
    epilog: list[str]
    deprecated: bool
    migrated: dict[str, JsonValue] | bool


class PluginCommandProperties(TypedDict):
    id: str
    name: str
    version: str
    website: str
    user_support_text: str
    description: str
    short_description: str
    actions: dict[str, ActionCommandProperties]


class RootCommandProperties(TypedDict):
    name: str
    help: str | None
    short_help: str | None
    builtins: list[str]


class BuiltinCommandProperties(TypedDict):
    name: str
    help: str | None
    short_help: str | None
    type: str
