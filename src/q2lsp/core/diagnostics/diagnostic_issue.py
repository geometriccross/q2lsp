"""Diagnostic issue type for QIIME2 command validation."""

from __future__ import annotations

from typing import NamedTuple


class DiagnosticIssue(NamedTuple):
    """A diagnostic issue for a command."""

    message: str  # The diagnostic message
    start: int  # Start offset in the document
    end: int  # End offset in the document (exclusive)
    code: str  # Diagnostic code (e.g., "q2lsp-dni/unknown-root")
