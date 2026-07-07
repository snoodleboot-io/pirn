"""``ToolStatus`` — terminal disposition of a single tool invocation."""

from __future__ import annotations

from enum import Enum


class ToolStatus(str, Enum):  # noqa: UP042 - str-mixin form is required for stable serialisation
    """Outcome classification for a :class:`ToolResult`.

    String-valued so the member serialises to a stable, human-readable
    token that survives round-trips through the DAG without depending on
    enum member ordering.

    Members
    -------
    OK:
        The tool completed and produced a value.
    ERROR:
        The tool raised or otherwise failed; ``error`` carries the detail.
    TIMEOUT:
        The invocation exceeded its allotted time budget.
    CANCELLED:
        The invocation was cancelled before completing.
    """

    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
