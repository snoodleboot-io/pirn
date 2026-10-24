"""``ValidatedToolCallFrame`` — lineage metadata for a :class:`ValidatedToolCall`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ValidatedToolCallFrame(PirnOpaqueValue):
    """What a tool call was validated against.

    Attributes
    ----------
    tool_name:
        The tool the call targets.
    declared_tools:
        The names of every tool the validator was given, in order.
    """

    tool_name: str
    declared_tools: tuple[str, ...]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"tool_name": self.tool_name, "declared_tools": list(self.declared_tools)}
