"""Example: Agent session v2 — dynamic DAG backed by pirn_agents.

Identical extensible-tapestry architecture as ``examples.llm_agent.agent_loop``:
a single extensible run grows with each iteration as knots register their
successors.

The difference from v1 is that every **action knot** is a real
``pirn_agents`` composite instead of an ad-hoc helper:

  llm_task   — ContextBuilder → LLMCall → OutputParser
  react      — ReActLoop (Reason+Act loop, 3 iterations)
  planner    — ContextBuilder → Planner → ToolRouter → ToolExecutor

All three return an ``AgentResponse`` so the aggregator sees a uniform type.

``ScriptedLLMProvider`` and ``StubTool`` (concrete implementations of the abstract
interfaces) live beside this module and are shared through ``StubToolbox``.
Swap them for a real provider by implementing ``LLMProvider.chat`` against your
vendor SDK.

Architecture (identical to ``examples.llm_agent.agent_loop``):
    AgentPlanner ──► action_0, action_1, ... (concurrent)
                 ──► Aggregator(all actions)
                 ──► AgentDecider(results=aggregator, ctx=self)

    AgentDecider: integrates results, then either
        ──► next AgentPlanner(ctx=self)      (more work to do)
        ──► _SessionFinalizer(state=self)    (session complete)

Run with:
    uv run python -m examples.llm_agent.agent_loop_v2
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from examples.llm_agent.agent_loop_v2.agent_planner import AgentPlanner
from examples.llm_agent.agent_loop_v2.session_config import SessionConfig
from examples.llm_agent.agent_loop_v2.session_context import SessionContext


class AgentLoopV2:
    """Builds and runs the one extensible tapestry that is a whole agent session."""

    _messages: ClassVar[tuple[str, ...]] = (
        "Research the latest developments in quantum computing and summarise",
        "Calculate compound interest on £5000 at 3.5% for 10 years",
        "Find our cancellation policy and draft a customer email explaining it",
        "Write a brief analysis of the weather patterns for our travel advisory",
        "I need a cost plan for our Pro tier renewals this quarter",
        "Summarise the key findings from the research into energy storage",
    )
    _type_icon: ClassVar[dict[str, str]] = {
        "llm_task": "💬",
        "react": "🔄",
        "planner": "📋",
        "agent": "🤖",
    }

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
        t.store.register(
            AgentPlanner(
                ctx=seed_ctx,
                _config=KnotConfig(id=AgentPlanner.planner_id(seed_ctx), validate_io=False),
            )
        )
        return t

    @classmethod
    async def main(cls) -> None:
        """Run one session end to end and print the per-message action trail."""
        history = SQLiteHistory(path=str(Path(__file__).resolve().parents[2] / "pirn.db"))
        ctx = cls.make_session(run_seed=random.randint(1, 2**31))
        t = cls.build_tapestry(initial_ctx=ctx, history=history)

        print("\n── Agent session v2 (pirn_agents) ──\n")

        result = await t.run(extensible=True)

        if not result.succeeded:
            exc = result.exceptions[0] if result.exceptions else None
            print(f"FAILED: {exc.knot_id if exc else '?'}: {exc.message[:120] if exc else ''}")
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
            if steps_summary:
                print(f"     {steps_summary}")
            print(f"     → {response[:100]}")
            print()

        history.close()
