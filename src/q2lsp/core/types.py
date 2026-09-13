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


class CompletionItem(NamedTuple):
    """Pure completion suggestion independent of transport protocol."""

    label: str
    detail: str
    kind: CompletionKind
    insert_text: str | None = None
