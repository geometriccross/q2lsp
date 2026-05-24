from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

QiimeCommandKind: TypeAlias = Literal["builtin", "plugin"]
QiimeOptionKind: TypeAlias = Literal[
    "input", "output", "parameter", "metadata", "unknown"
]


@dataclass(frozen=True)
class QiimeRootFact:
    name: str
    summary: str
    help_text: str


@dataclass(frozen=True)
class QiimeCommandFact:
    name: str
    kind: QiimeCommandKind
    summary: str
    help_text: str
    has_actions: bool


@dataclass(frozen=True)
class QiimeActionFact:
    command_name: str
    name: str
    summary: str
    help_text: str


@dataclass(frozen=True)
class QiimeOptionFact:
    name: str
    label: str
    kind: QiimeOptionKind
    required: bool
    description: str
    value_type: str = ""
    is_bool_flag: bool = False
