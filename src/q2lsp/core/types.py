"""Core domain types for completion flow."""

from __future__ import annotations

from typing import Literal, NamedTuple, TypeAlias

CompletionMode: TypeAlias = Literal["root", "plugin", "parameter", "none"]
CompletionKind: TypeAlias = Literal["plugin", "action", "parameter", "builtin"]

COMPLETION_MODE_ROOT: CompletionMode = "root"
COMPLETION_MODE_PLUGIN: CompletionMode = "plugin"
COMPLETION_MODE_PARAMETER: CompletionMode = "parameter"
COMPLETION_MODE_NONE: CompletionMode = "none"

COMPLETION_KIND_PLUGIN: CompletionKind = "plugin"
COMPLETION_KIND_ACTION: CompletionKind = "action"
COMPLETION_KIND_PARAMETER: CompletionKind = "parameter"
COMPLETION_KIND_BUILTIN: CompletionKind = "builtin"


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
