"""``RoutedToolCallFrame`` — lineage metadata for a :class:`RoutedToolCall`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class RoutedToolCallFrame(PirnOpaqueValue):
    """How a plan step was routed to a tool.

    Attributes
    ----------
    step:
        The plan step text that was routed.
    tool_name:
        The tool the step was matched to.
    candidates:
        The names of every tool the router could choose from, in order.
    """

    step: str
    tool_name: str
    candidates: tuple[str, ...]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"step": self.step, "tool_name": self.tool_name, "candidates": list(self.candidates)}
