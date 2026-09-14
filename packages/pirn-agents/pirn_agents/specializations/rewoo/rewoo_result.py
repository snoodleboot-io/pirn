"""``ReWooResult`` — the typed outcome of a ReWOO run."""

from __future__ import annotations

from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.rewoo.rewoo_frame import ReWooFrame
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_result import ToolResult


class ReWooResult(AgentResult[ReWooFrame, str]):
    """Outcome of a ReWOO plan-execute-synthesise run.

    ``ReWooResult`` is ``Payload[ReWooFrame, str]`` (PIR-868, following the
    ADR agents-speaks-core WS6b pattern) — ``data`` is the synthesised final
    answer text, and ``metadata`` is the :class:`ReWooFrame` carrying the
    up-front plan and the gathered tool results. The constructor takes the pattern's named
    fields (``answer``, ``plan``, ``results``), and each is also a read-only property.
    """

    def __init__(
        self, answer: str, plan: tuple[ToolCall, ...], results: tuple[ToolResult, ...]
    ) -> None:
        frame = ReWooFrame(plan=plan, results=results)
        super().__init__(metadata=frame, data=answer)

    @property
    def answer(self) -> str:
        return self._data

    @property
    def plan(self) -> tuple[ToolCall, ...]:
        return self._metadata.plan

    @property
    def results(self) -> tuple[ToolResult, ...]:
        return self._metadata.results

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["answer"] = self.answer
        return audit
