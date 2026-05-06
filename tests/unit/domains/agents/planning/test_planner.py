"""Unit tests for :class:`Planner`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.agents.planning.planner import Planner
from pirn.domains.agents.types.agent_context import AgentContext
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.domains.agents.types.plan import Plan
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> Planner:
    @knot
    async def _ctx() -> AgentContext:
        return AgentContext(messages=())

    with Tapestry():
        upstream = _ctx(_config=KnotConfig(id="ctx"))
        return Planner(context=upstream, llm=llm, _config=KnotConfig(id="p"))


_CONTEXT = AgentContext(
    messages=(AgentMessage(role="user", content="plan a trip"),),
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_parses_numbered_steps(self) -> None:
        llm = StubLLMProvider(
            responses=["1. book flight\n2. reserve hotel\n3. pack bags"]
        )
        k = _make_knot(llm)
        plan: Plan = await k.process(context=_CONTEXT, llm=llm)
        assert plan.steps == ("book flight", "reserve hotel", "pack bags")

    async def test_collects_rationale_lines(self) -> None:
        llm = StubLLMProvider(
            responses=[
                "# user wants to travel\n"
                "1. book flight\n"
                "# choose nearest airport\n"
                "2. pack bags"
            ]
        )
        k = _make_knot(llm)
        plan: Plan = await k.process(context=_CONTEXT, llm=llm)
        assert plan.steps == ("book flight", "pack bags")
        assert "user wants to travel" in plan.rationale

    async def test_raises_when_no_steps(self) -> None:
        llm = StubLLMProvider(responses=["# only rationale"])
        k = _make_knot(llm)
        with self.assertRaises(ValueError):
            await k.process(context=_CONTEXT, llm=llm)

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(responses=["1. step"])
        k = _make_knot(llm)
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            await k.process(
                context=_CONTEXT,
                llm="bad",  # type: ignore[arg-type]
            )
