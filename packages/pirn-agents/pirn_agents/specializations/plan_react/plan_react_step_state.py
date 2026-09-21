"""``PlanReActStepState`` — the value threaded through the plan-step ReAct loop.

A :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`, not a plain frozen
dataclass, because it carries the live ``Tool`` objects each step's loop may
call. A knot is not describable to pydantic, so a plain state holding tools
cannot be validated at the loop's boundary at all; the mixin is core's answer for
exactly that — "frozen dataclass wrappers with non-pydantic fields" — and
:meth:`_pirn_audit_dict` keeps the lineage-relevant fields visible while the live
tools stay out of serialisation (PIR-874).

The alternative was holding the tools on the loop instance, which is graph state:
the knot object is shared by every run of its tapestry, so two concurrent runs
would overwrite each other (knot-design-rules Rule 4).

Internal API. See ``plan_react_step_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.tools.tool import Tool
from pirn_agents.types.messaging.agent_response import AgentResponse


@dataclass(frozen=True)
class PlanReActStepState(PirnOpaqueValue):
    """One plan step's worth of accumulated state.

    Frozen; ``fold`` returns a new instance rather than mutating, matching every
    other ``LoopSubTapestry`` state in this package.

    Attributes:
        steps: The plan's ordered step descriptions, fixed for the loop's life.
        llm: The provider each step's ReAct loop calls.
        tools: The tools each step's ReAct loop may use.
        max_iterations: The per-step bound on ReAct iterations.
        responses: Each completed step's response, in step order.
        index: The index of the next step to execute.
    """

    steps: tuple[str, ...]
    llm: LLMProvider
    tools: tuple[Tool, ...]
    max_iterations: int
    responses: tuple[AgentResponse, ...] = ()
    index: int = 0

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return the lineage-relevant fields, leaving the live collaborators out.

        The provider and the tools are live resources; a run's history wants to
        know *which step* it is on and *how far* it has got, not a token for a
        provider it cannot replay anyway.
        """
        return {
            "steps": list(self.steps),
            "max_iterations": self.max_iterations,
            "responses_collected": len(self.responses),
            "index": self.index,
            "tool_count": len(self.tools),
        }
