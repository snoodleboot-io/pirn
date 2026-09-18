"""``AgentPlanner`` — plans the next actions and grows the running tapestry.

Part of the ``examples.llm_agent.agent_loop`` example.
"""

from __future__ import annotations

import re
from typing import ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.aggregator import Aggregator
from pirn.tapestry import Tapestry

from examples.llm_agent.agent_loop.agent_decider import AgentDecider
from examples.llm_agent.agent_loop.knots import run_mcp_call, run_tool_call
from examples.llm_agent.agent_loop.planned_action import PlannedAction
from examples.llm_agent.agent_loop.session_config import SessionConfig
from examples.llm_agent.agent_loop.session_context import SessionContext
from examples.llm_agent.agent_loop.sub_agent_runner import SubAgentRunner


class AgentPlanner(Knot):
    """Plans the next set of actions and registers them directly into the running tapestry.

    Outputs the updated context (with bumped iteration counters) so that action
    knots wired to ``ctx=self`` receive it as a data input.
    """

    _weather_locations: ClassVar[tuple[str, ...]] = (
        "London",
        "Tokyo",
        "New York",
        "Paris",
        "Berlin",
    )
    _calculate_expressions: ClassVar[tuple[str, ...]] = (
        "150 * 1.2",
        "5000 * 0.035 * 10",
        "280 * 0.15",
        "99 * 12",
    )
    _research_services: ClassVar[tuple[str, ...]] = ("web_search", "kb_search")
    _subagent_names: ClassVar[tuple[str, ...]] = ("summarise", "draft_email", "analyse")
    _extra_action_chance: ClassVar[float] = 0.35
    _synthesis_chance: ClassVar[float] = 0.6

    @staticmethod
    def planner_id(ctx: SessionContext) -> str:
        """Short human-readable ID for an AgentPlanner from message content + position."""
        words = re.sub(r"[^a-z0-9\s]", "", ctx.current_message.lower()).split()[:3]
        slug = "_".join(words)
        return f"{slug}__m{ctx.msg_idx + 1}i{ctx.msg_iteration + 1}"

    @classmethod
    def plan_next_actions(cls, ctx: SessionContext) -> list[PlannedAction]:
        """Plan the next actions for the current message.

        Seeds the RNG from (current_message, run_seed, iteration) so the same
        message with a different seed produces a different action mix.  Later
        iterations lean toward synthesis; earlier ones gather data in parallel.
        """
        rng = ctx.rng(extra="plan")
        task = ctx.current_message.lower()
        msg_steps = [s for s in ctx.scratchpad if s.msg_idx == ctx.msg_idx]

        if msg_steps and ctx.msg_iteration >= 2:
            past_budget = ctx.msg_iteration >= SessionConfig.max_iterations_per_msg - 1
            if rng.random() < cls._synthesis_chance or past_budget:
                context = " | ".join(s.output for s in msg_steps[-3:])
                return [PlannedAction("subagent", "summarise", {"context": context})]

        actions: list[PlannedAction] = []

        if "weather" in task:
            n_locs = rng.randint(1, min(3, 1 + ctx.msg_iteration))
            chosen = rng.sample(cls._weather_locations, n_locs)
            actions += [
                PlannedAction("tool_call", "get_weather", {"location": loc}) for loc in chosen
            ]

        if any(w in task for w in ["calculat", "percent", "interest", "cost"]):
            expr = rng.choice(cls._calculate_expressions)
            actions.append(PlannedAction("tool_call", "calculate", {"expression": expr}))

        if any(w in task for w in ["research", "find", "look up", "search"]):
            mcp_name = rng.choice(cls._research_services)
            actions.append(PlannedAction("mcp_call", mcp_name, {"query": task[:60]}))

        if any(w in task for w in ["policy", "refund", "cancel", "plan"]):
            actions.append(PlannedAction("mcp_call", "kb_search", {"query": task[:50]}))

        if any(w in task for w in ["write", "draft", "email", "report", "summarise", "summary"]):
            context = " | ".join(s.output for s in msg_steps) or task
            sub_name = rng.choice(cls._subagent_names)
            actions.append(PlannedAction("subagent", sub_name, {"context": context[:200]}))

        if any(w in task for w in ["url", "page", "fetch", "scrape"]):
            actions.append(PlannedAction("mcp_call", "fetch_url", {"url": "https://example.com"}))

        if not actions:
            actions.append(
                rng.choice(
                    [
                        PlannedAction("mcp_call", "web_search", {"query": task[:60]}),
                        PlannedAction("tool_call", "get_weather", {"location": "London"}),
                        PlannedAction("subagent", "analyse", {"context": task}),
                    ]
                )
            )

        msg_types = {s.action_type for s in msg_steps}
        if (
            rng.random() < cls._extra_action_chance
            and len(actions) < 4
            and "subagent" not in msg_types
        ):
            actions.append(
                rng.choice(
                    [
                        PlannedAction("mcp_call", "web_search", {"query": f"{task[:30]} latest"}),
                        PlannedAction("tool_call", "calculate", {"expression": "100 * 1.035 ** 5"}),
                    ]
                )
            )

        return actions

    async def process(self, ctx: SessionContext, **_) -> SessionContext:
        new_ctx = ctx.evolve(iteration=ctx.iteration + 1, msg_iteration=ctx.msg_iteration + 1)
        actions = self.plan_next_actions(new_ctx)

        store = Tapestry.current_store()
        if store is None:
            return new_ctx

        prefix = self.knot_id
        action_knots: dict[str, Knot] = {}

        for i, action in enumerate(actions):
            node_id = f"{prefix}__act_{i}"
            if action.action_type == "tool_call":
                ak: Knot = run_tool_call(
                    action=action, ctx=self, _config=KnotConfig(id=node_id, validate_io=False)
                )
            elif action.action_type == "mcp_call":
                ak = run_mcp_call(
                    action=action, ctx=self, _config=KnotConfig(id=node_id, validate_io=False)
                )
            else:
                ak = SubAgentRunner(
                    action=action, ctx=self, _config=KnotConfig(id=node_id, validate_io=False)
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
