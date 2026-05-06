"""The outcome of a single :class:`ToolCall`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


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
    """

    call_id: str
    result: Any
    error: str | None = None

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "result": repr(self.result),
            "error": self.error,
        }
