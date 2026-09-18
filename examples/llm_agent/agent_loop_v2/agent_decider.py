"""``AgentDecider`` — integrates ``AgentResponse`` results and grows the tapestry.

Part of the ``examples.llm_agent.agent_loop_v2`` example.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_agents.types.messaging.agent_response import AgentResponse

from examples.llm_agent.agent_loop_v2.session_config import SessionConfig
from examples.llm_agent.agent_loop_v2.session_context import SessionContext
from examples.llm_agent.agent_loop_v2.session_finalizer import _SessionFinalizer
from examples.llm_agent.agent_loop_v2.step_result import StepResult


class AgentDecider(Knot):
    """Integrates AgentResponse results and spawns the next planner or finaliser."""

    _enough_chance: ClassVar[float] = 0.55
    _summary_length: ClassVar[int] = 120

    async def process(
        self,
        results: list[AgentResponse],
        ctx: SessionContext,
        **_: Any,
    ) -> SessionContext:
        step_results = tuple(
            StepResult(
                iteration=ctx.iteration,
                msg_idx=ctx.msg_idx,
                action_type="agent",
                name=f"step_{j}",
                response=r,
            )
            for j, r in enumerate(results)
            if isinstance(r, AgentResponse)
        )
        new_ctx = ctx.evolve(scratchpad=ctx.scratchpad + step_results)

        rng = new_ctx.rng(extra="termination")
        msg_steps = [s for s in new_ctx.scratchpad if s.msg_idx == new_ctx.msg_idx]

        synthesised = any(
            "Final Answer" in s.response.data or "synthesise" in s.response.data
            for s in step_results
        )
        enough = len(msg_steps) >= 2 and rng.random() < self._enough_chance

        if synthesised or enough or new_ctx.msg_iteration >= SessionConfig.max_iterations_per_msg:
            best = max(step_results, key=lambda s: len(s.response.data), default=None)
            summary = best.response.data[: self._summary_length] if best else "Completed."
            new_ctx = new_ctx.evolve(
                responses=(*new_ctx.responses, summary),
                msg_idx=new_ctx.msg_idx + 1,
                msg_iteration=0,
            )

        store = Tapestry.current_store()
        if store is None:
            return new_ctx

        if not new_ctx.done and new_ctx.iteration < SessionConfig.max_total_iterations:
            # Deferred: AgentPlanner imports AgentDecider to wire its own successor, so
            # the two knots are mutually recursive by construction — the graph alternates
            # planner → decider → planner for the life of the session.
            from examples.llm_agent.agent_loop_v2.agent_planner import AgentPlanner

            store.register(
                AgentPlanner(
                    ctx=self,
                    _config=KnotConfig(id=AgentPlanner.planner_id(new_ctx), validate_io=False),
                )
            )
        else:
            store.register(
                _SessionFinalizer(
                    state=self,
                    _config=KnotConfig(id=SessionConfig.session_complete_id, validate_io=False),
                )
            )

        return new_ctx
