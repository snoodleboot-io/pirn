"""Unit tests for :class:`Planner`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.planning.planner import Planner
from pirn.domains.agents.types.agent_context import AgentContext
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.domains.agents.types.plan import Plan
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.conftest import StubLLMProvider


@knot
async def emit_context() -> AgentContext:
    return AgentContext(
        messages=(AgentMessage(role="user", content="plan a trip"),),
    )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_parses_numbered_steps(self) -> None:
        llm = StubLLMProvider(
            responses=["1. book flight\n2. reserve hotel\n3. pack bags"]
        )
        with Tapestry() as t:
            ctx = emit_context(_config=KnotConfig(id="ctx"))
            Planner(context=ctx, llm=llm, _config=KnotConfig(id="p"))
        result = await t.run(RunRequest())
        plan: Plan = result.outputs["p"]
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
        with Tapestry() as t:
            ctx = emit_context(_config=KnotConfig(id="ctx"))
            Planner(context=ctx, llm=llm, _config=KnotConfig(id="p"))
        result = await t.run(RunRequest())
        plan: Plan = result.outputs["p"]
        assert plan.steps == ("book flight", "pack bags")
        assert "user wants to travel" in plan.rationale

    async def test_raises_when_no_steps(self) -> None:
        llm = StubLLMProvider(responses=["# only rationale"])
        with Tapestry() as t:
            ctx = emit_context(_config=KnotConfig(id="ctx"))
            Planner(context=ctx, llm=llm, _config=KnotConfig(id="p"))
        result = await t.run(RunRequest())
        assert "p" not in result.outputs


class TestConstruction(unittest.TestCase):
    def test_requires_llm_provider(self) -> None:
        @knot
        async def empty() -> AgentContext:
            return AgentContext(messages=())

        with Tapestry():
            ctx = empty(_config=KnotConfig(id="ctx"))
            with self.assertRaisesRegex(TypeError, "LLMProvider"):
                Planner(
                    context=ctx,
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="p"),
                )
