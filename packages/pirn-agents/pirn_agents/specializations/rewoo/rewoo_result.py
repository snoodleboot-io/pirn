"""``ReWooResult`` — the typed outcome of a ReWOO run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_result import ToolResult


@dataclass(frozen=True)
class ReWooResult(PirnOpaqueValue):
    """Outcome of a ReWOO plan-execute-synthesise run.

    Attributes
    ----------
    answer:
        The synthesised final answer text.
    plan:
        The full tuple of :class:`ToolCall`s planned up front, before any
        execution — the decoupling that distinguishes ReWOO from ReAct.
    results:
        The :class:`ToolResult`s gathered from executing ``plan`` in parallel,
        in plan order.
    """

    answer: str
    plan: tuple[ToolCall, ...]
    results: tuple[ToolResult, ...]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "plan": [call._pirn_audit_dict() for call in self.plan],
            "results": [result._pirn_audit_dict() for result in self.results],
        }
