"""Core domain types for completion flow."""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple


class _StrEnum(str, Enum):
    """String-valued enum that behaves like str at runtime."""

    def __str__(self) -> str:
        return str(self.value)


class CompletionMode(_StrEnum):
    """Mode determines what kind of completions to offer."""

    ROOT = "root"
    PLUGIN = "plugin"
    PARAMETER = "parameter"
    NONE = "none"


class CompletionKind(_StrEnum):
    """Kind categorizes completion items."""

    PLUGIN = "plugin"
    ACTION = "action"
    PARAMETER = "parameter"
    BUILTIN = "builtin"


class CompletionQuery(NamedTuple):
    """Pure input for completion decisions."""

    mode: CompletionMode
    prefix: str
    normalized_prefix: str = ""
    plugin_name: str = ""
    action_name: str = ""
    used_parameters: frozenset[str] = frozenset()


class CompletionItem(NamedTuple):
    """Pure completion suggestion independent of transport protocol."""

    label: str
    detail: str
    kind: CompletionKind
    insert_text: str | None = None


class ParameterCandidate(NamedTuple):
    """Normalized parameter data used by completion filtering."""

    name: str
    item: CompletionItem
    match_texts: tuple[str, ...] = ()


class ActionCandidate(NamedTuple):
    """Normalized action data and its available parameters."""

    item: CompletionItem
    parameters: tuple[ParameterCandidate, ...] = ()


class CommandCandidate(NamedTuple):
    """Normalized plugin/builtin command data for completions."""

    name: str
    is_builtin: bool
    actions: tuple[ActionCandidate, ...] = ()


class CompletionData(NamedTuple):
    """Normalized completion dataset consumed by the core engine."""

    root_items: tuple[CompletionItem, ...] = ()
    commands: tuple[CommandCandidate, ...] = ()
