"""``AgentPlanner`` — picks the next agent composites and grows the running tapestry.

Part of the ``examples.llm_agent.agent_loop_v2`` example.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.aggregator import Aggregator
from pirn.tapestry import Tapestry

from examples.llm_agent.agent_loop_v2.agent_decider import AgentDecider
from examples.llm_agent.agent_loop_v2.llm_task_runner import LLMTaskRunner
from examples.llm_agent.agent_loop_v2.planned_action import PlannedAction
from examples.llm_agent.agent_loop_v2.planner_runner import PlannerRunner
from examples.llm_agent.agent_loop_v2.react_runner import ReActRunner
from examples.llm_agent.agent_loop_v2.session_config import SessionConfig
from examples.llm_agent.agent_loop_v2.session_context import SessionContext


class AgentPlanner(Knot):
    """Plans next actions and registers the appropriate agent knots.

    Each action becomes a real ``pirn_agents`` SubTapestry:
    ``LLMTaskRunner``, ``ReActRunner``, or ``PlannerRunner``.
    """

    _synthesis_chance: ClassVar[float] = 0.6
    _extra_action_chance: ClassVar[float] = 0.25

    @staticmethod
    def planner_id(ctx: SessionContext) -> str:
        """Short human-readable ID for an AgentPlanner from message content + position."""
        words = re.sub(r"[^a-z0-9\s]", "", ctx.current_message.lower()).split()[:3]
        slug = "_".join(words)
        return f"{slug}__m{ctx.msg_idx + 1}i{ctx.msg_iteration + 1}"

    @classmethod
    def plan_next_actions(cls, ctx: SessionContext) -> list[PlannedAction]:
        """Pick action types for this iteration.

        Later iterations lean toward synthesis (llm_task); early iterations
        prefer data-gathering (react/planner).
        """
        rng = ctx.rng(extra="plan")
        task = ctx.current_message.lower()
        msg_steps = [s for s in ctx.scratchpad if s.msg_idx == ctx.msg_idx]

        if msg_steps and ctx.msg_iteration >= 2:
            past_budget = ctx.msg_iteration >= SessionConfig.max_iterations_per_msg - 1
            if rng.random() < cls._synthesis_chance or past_budget:
                return [PlannedAction("llm_task", "synthesise")]

        actions: list[PlannedAction] = []

        if any(w in task for w in ["research", "find", "search", "explain", "quantum"]):
            actions.append(PlannedAction("react", "research"))

        if any(w in task for w in ["calculat", "percent", "interest", "cost", "plan"]):
            actions.append(PlannedAction("planner", "compute"))

        if any(w in task for w in ["write", "draft", "email", "report", "summarise", "summary"]):
            actions.append(PlannedAction("llm_task", "draft"))

        if any(w in task for w in ["weather", "forecast", "advisory"]):
            actions.append(PlannedAction("react", "weather_lookup"))

        if any(w in task for w in ["policy", "refund", "cancel", "lookup"]):
            actions.append(PlannedAction("planner", "policy_lookup"))

        if not actions:
            actions.append(
                rng.choice(
                    [
                        PlannedAction("react", "explore"),
                        PlannedAction("llm_task", "analyse"),
                        PlannedAction("planner", "investigate"),
                    ]
                )
            )

        if rng.random() < cls._extra_action_chance and len(actions) < 3:
            actions.append(PlannedAction("llm_task", "context_build"))

        return actions

    async def process(self, ctx: SessionContext, **_: Any) -> SessionContext:
        new_ctx = ctx.evolve(iteration=ctx.iteration + 1, msg_iteration=ctx.msg_iteration + 1)
        actions = self.plan_next_actions(new_ctx)

        store = Tapestry.current_store()
        if store is None:
            return new_ctx

        prefix = self.knot_id
        action_knots: dict[str, Knot] = {}

        for i, action in enumerate(actions):
            node_id = f"{prefix}__act_{i}"
            if action.action_type == "react":
                ak: Knot = ReActRunner(
                    ctx=self,
                    action=action,
                    _config=KnotConfig(id=node_id, validate_io=False),
                )
            elif action.action_type == "planner":
                ak = PlannerRunner(
                    ctx=self,
                    action=action,
                    _config=KnotConfig(id=node_id, validate_io=False),
                )
            else:
                ak = LLMTaskRunner(
                    ctx=self,
                    action=action,
                    _config=KnotConfig(id=node_id, validate_io=False),
                )
            store.register(ak)
            action_knots[f"r{i}"] = ak

        agg = Aggregator(
            combine=lambda **kw: list(kw.values()),
            _config=KnotConfig(id=f"{prefix}__agg", validate_io=False),
            **action_knots,
        )
        store.register(agg)

        decider = AgentDecider(
            results=agg,
            ctx=self,
            _config=KnotConfig(id=f"{prefix}__decide", validate_io=False),
        )
        store.register(decider)

        return new_ctx
