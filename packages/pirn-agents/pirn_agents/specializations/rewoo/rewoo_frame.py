"""``ReWooFrame`` — lineage metadata for a :class:`ReWooResult`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_result import ToolResult


@dataclass(frozen=True)
class ReWooFrame(PirnOpaqueValue):
    """Run-level facts for a ReWOO plan-execute-synthesise run.

    The frame half of the ``Payload[ReWooFrame, str]`` split (PIR-868).

    Attributes
    ----------
    plan:
        The full tuple of :class:`ToolCall`s planned up front, before any
        execution — the decoupling that distinguishes ReWOO from ReAct.
    results:
        The :class:`ToolResult`s gathered from executing ``plan`` in parallel,
        in plan order.
    """

    plan: tuple[ToolCall, ...]
    results: tuple[ToolResult, ...]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        plan: tuple[PirnOpaqueValue, ...] = self.plan
        results: tuple[PirnOpaqueValue, ...] = self.results
        return {
            "plan": [call._pirn_audit_dict() for call in plan],
            "results": [result._pirn_audit_dict() for result in results],
        }
