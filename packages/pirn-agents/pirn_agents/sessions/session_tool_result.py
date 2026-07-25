"""``SessionToolResult`` — a tool invocation's outcome recorded in run state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class SessionToolResult(PirnOpaqueValue):
    """A JSON-serialisable record of one tool call's result.

    Distinct from :class:`pirn_agents.types.tool_result.ToolResult` (whose
    ``result`` is any python object): a checkpoint must round-trip through a
    JSON payload, so this value keeps only a serialisable ``output``.

    Attributes
    ----------
    call_id:
        Identifier of the originating tool call.
    tool_name:
        Name of the tool that produced the result.
    output:
        JSON-serialisable output value the tool returned.
    """

    call_id: str
    tool_name: str
    output: Any = None

    def __post_init__(self) -> None:
        if not isinstance(self.call_id, str) or not self.call_id:
            raise TypeError("SessionToolResult: call_id must be a non-empty str")
        if not isinstance(self.tool_name, str) or not self.tool_name:
            raise TypeError("SessionToolResult: tool_name must be a non-empty str")

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this result."""
        return {"call_id": self.call_id, "tool_name": self.tool_name, "output": self.output}

    @classmethod
    def from_payload(cls, payload: Any) -> SessionToolResult:
        """Reconstruct a result from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"SessionToolResult.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        return cls(
            call_id=str(payload["call_id"]),
            tool_name=str(payload["tool_name"]),
            output=payload.get("output"),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
