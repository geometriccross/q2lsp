"""Shared models for diagnostics collection."""

from __future__ import annotations

from typing import NamedTuple

from q2lsp.lsp.diagnostics.diagnostic_issue import DiagnosticIssue
from q2lsp.lsp.types import ParsedCommand


class DependencyReference(NamedTuple):
    """A dependency path reference anchored in the document."""

    path: str
    start: int
    end: int
    option_start: int
    option_end: int

    @property
    def anchor_start(self) -> int:
        if self.start < self.end:
            return self.start
        return self.option_start

    @property
    def anchor_end(self) -> int:
        if self.start < self.end:
            return self.end
        return self.option_end


class CommandDependencies(NamedTuple):
    """Dependency references extracted from a command."""

    inputs: tuple[DependencyReference, ...] = ()
    outputs: tuple[DependencyReference, ...] = ()


class CommandAnalysis(NamedTuple):
    """Command-level diagnostics and extracted dependency references."""

    command: ParsedCommand
    issues: tuple[DiagnosticIssue, ...]
    dependencies: CommandDependencies
