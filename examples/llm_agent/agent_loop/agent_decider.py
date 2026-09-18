"""``AgentDecider`` — integrates action results and spawns the next planner or terminal.

Part of the ``examples.llm_agent.agent_loop`` example.
"""

from __future__ import annotations

from typing import ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from examples.llm_agent.agent_loop.session_config import SessionConfig
from examples.llm_agent.agent_loop.session_context import SessionContext
from examples.llm_agent.agent_loop.session_finalizer import _SessionFinalizer
from examples.llm_agent.agent_loop.step_result import StepResult


class AgentDecider(Knot):
    """Integrates action results, updates context, and spawns the next planner or terminal.

    ``results`` arrives from the aggregator (a real data edge).
    ``ctx`` arrives from the planner that spawned this decider (a real data edge).
    """

    _resolution_chance: ClassVar[float] = 0.5

    async def process(self, results: list[StepResult], ctx: SessionContext, **_) -> SessionContext:
        new_scratchpad = ctx.scratchpad + tuple(results)
        new_ctx = ctx.evolve(scratchpad=new_scratchpad)

        # Resolved when a synthesis subagent ran.
        if results and results[-1].action_type == "subagent":
            new_ctx = new_ctx.evolve(
                responses=(*new_ctx.responses, results[-1].output),
                msg_idx=new_ctx.msg_idx + 1,
                msg_iteration=0,
            )
        else:
            rng = new_ctx.rng(extra="termination")
            msg_steps = [s for s in new_scratchpad if s.msg_idx == new_ctx.msg_idx]
            if len(msg_steps) >= 2 and rng.random() < self._resolution_chance:
                ctx_str = " | ".join(s.output for s in msg_steps[-3:])
                new_ctx = new_ctx.evolve(
                    responses=(
                        *new_ctx.responses,
                        f"Resolved after {new_ctx.msg_iteration} iterations: {ctx_str[:120]}",
                    ),
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
            from examples.llm_agent.agent_loop.agent_planner import AgentPlanner

            next_id = AgentPlanner.planner_id(new_ctx)
            store.register(
                AgentPlanner(ctx=self, _config=KnotConfig(id=next_id, validate_io=False))
            )
        else:
            store.register(
                _SessionFinalizer(
                    state=self,
                    _config=KnotConfig(id=SessionConfig.session_complete_id, validate_io=False),
                )
            )

        return new_ctx
