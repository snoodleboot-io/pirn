"""Example: Agentic session as a true dynamic DAG.

A single session receives a sequence of messages and works through them
iteratively.  The whole session is ONE extensible run — the graph grows with
each iteration as knots register their successors directly.

Architecture:

    AgentPlanner → action_0, action_1, ... (concurrent)
                 → Aggregator(all actions)
                 → AgentDecider(results=aggregator, ctx=self)

    AgentDecider: integrates results, then either
        → next AgentPlanner(ctx=self)      (more work to do)
        → _SessionFinalizer(state=self)    (session complete)

Every knot is a direct node in a single extensible tapestry run.  Data flows
through real parent edges — there is no shared mutable state blob.

Action types:
- ``tool_call``  — local function (weather, calculator)
- ``mcp_call``   — simulated remote service (web search, knowledge base)
- ``subagent``   — inner tapestry with its own two-step pipeline

Run with:
    uv run python -m examples.llm_agent.agent_loop
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from examples.llm_agent.agent_loop.agent_planner import AgentPlanner
from examples.llm_agent.agent_loop.session_config import SessionConfig
from examples.llm_agent.agent_loop.session_context import SessionContext


class AgentLoop:
    """Builds and runs the one extensible tapestry that is a whole agent session."""

    _messages: ClassVar[tuple[str, ...]] = (
        "What's the weather forecast for my trip to London and Tokyo?",
        "Calculate the compound interest on £5000 at 3.5% for 10 years",
        "Research the latest developments in quantum computing and summarise for me",
        "Find our cancellation policy and draft a customer email explaining it",
        "I need a cost analysis for our Pro plan renewals this quarter",
        "What's the weather in New York and write a brief travel advisory",
    )
    _type_icon: ClassVar[dict[str, str]] = {
        "tool_call": "⚙",
        "mcp_call": "🌐",
        "subagent": "🤖",
    }

    @classmethod
    def messages(cls) -> tuple[str, ...]:
        """The fixed conversation this example replays."""
        return cls._messages

    @classmethod
    def make_session(cls, run_seed: int = 1) -> SessionContext:
        """Seed context for one session over the fixed conversation."""
        return SessionContext(messages=cls._messages, run_seed=run_seed)

    @classmethod
    def build_tapestry(
        cls,
        *,
        initial_ctx: SessionContext | None = None,
        history: SQLiteHistory | None = None,
    ) -> Tapestry:
        """Register the first planner into an otherwise empty extensible tapestry."""
        t = Tapestry(history=history)
        seed_ctx = initial_ctx or cls.make_session()
        first_planner = AgentPlanner(
            ctx=seed_ctx,
            _config=KnotConfig(id=AgentPlanner.planner_id(seed_ctx), validate_io=False),
        )
        t.store.register(first_planner)
        return t

    @classmethod
    async def main(cls) -> None:
        """Run one session end to end and print the per-message action trail."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))
        ctx = cls.make_session(run_seed=random.randint(1, 2**31))
        t = cls.build_tapestry(initial_ctx=ctx, history=history)

        print("\n── Agent session ──\n")

        result = await t.run(extensible=True)

        if not result.succeeded:
            exc = result.exceptions[0] if result.exceptions else None
            print(f"FAILED: {exc.knot_id if exc else '?'}: {exc.message[:80] if exc else ''}")
            history.close()
            return

        final: SessionContext = result.outputs[SessionConfig.session_complete_id]
        print(f"{len(final.messages)} messages · {final.iteration} total iterations\n")

        for i, (msg, response) in enumerate(zip(final.messages, final.responses, strict=True)):
            msg_steps = [s for s in final.scratchpad if s.msg_idx == i]
            steps_summary = "  ".join(
                f"{cls._type_icon.get(s.action_type, '·')}{s.name}" for s in msg_steps
            )
            print(f"[{i + 1}] {msg[:70]}")
            print(f"     {steps_summary}")
            print(f"     → {response[:100]}")
            print()

        history.close()
