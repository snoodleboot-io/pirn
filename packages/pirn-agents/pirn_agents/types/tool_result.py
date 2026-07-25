"""The outcome of a single :class:`ToolCall`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.types.tool_status import ToolStatus


@dataclass(frozen=True)
class ToolResult(PirnOpaqueValue):
    """Result returned by invoking a tool.

    Attributes
    ----------
    call_id:
        Identifier matching the originating :class:`ToolCall`.
    result:
        Raw value the tool produced. May be any python object.
    error:
        Stringified exception when the invocation failed; ``None``
        otherwise.
    status:
        Terminal disposition of the invocation. Defaults to
        :attr:`ToolStatus.OK`; when left at the default and ``error`` is
        set, it is promoted to :attr:`ToolStatus.ERROR` in
        ``__post_init__``. An explicit non-OK status (``TIMEOUT``) is
        always preserved.
    latency:
        Wall-clock duration of the invocation in seconds, or ``None`` when
        not measured.
    tokens:
        Token count attributable to the invocation, or ``None`` when not
        measured.
    """

    call_id: str
    result: Any
    error: str | None = None
    status: ToolStatus = ToolStatus.OK
    latency: float | None = None
    tokens: int | None = None

    def __post_init__(self) -> None:
        """Derive ``status`` from ``error`` when left at its default.

        Frozen-safe: uses ``object.__setattr__`` to mutate the field. Only
        promotes the default ``OK`` to ``ERROR`` so an explicitly supplied
        ``TIMEOUT`` status is never overwritten.
        """
        if self.error is not None and self.status == ToolStatus.OK:
            object.__setattr__(self, "status", ToolStatus.ERROR)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "result": repr(self.result),
            "error": self.error,
            "status": self.status.value,
            "latency": self.latency,
            "tokens": self.tokens,
        }
