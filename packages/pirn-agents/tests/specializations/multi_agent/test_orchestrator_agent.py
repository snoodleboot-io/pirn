"""Tests for :class:`OrchestratorAgent`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.specializations.multi_agent.orchestrator_agent import (
    OrchestratorAgent,
)
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider

_SPEC_REGISTRY: dict[str, str] = {}


class StubSpecialist(SubTapestry):
    """SubTapestry double that emits a fixed AgentResponse for any task."""

    def __init__(self, *, task: Any = "", _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str = "", **_: Any) -> AgentResponse:
        reply = _SPEC_REGISTRY.get(self.config.id, "specialist-reply")
        return AgentResponse(content=f"{reply}:{task}", finish_reason="stop")


def _make_spec(reply: str, id_: str) -> StubSpecialist:
    _SPEC_REGISTRY[id_] = reply
    with Tapestry():
        return StubSpecialist(_config=KnotConfig(id=id_))


def _make_knot(llm: StubLLMProvider, specialists: dict) -> OrchestratorAgent:
    with Tapestry():
        return OrchestratorAgent(
            task="ask",
            llm=llm,
            specialists=specialists,
            _config=KnotConfig(id="orch"),
        )


class TestOrchestratorAgentProcess(unittest.IsolatedAsyncioTestCase):
    async def test_routes_to_named_specialist(self) -> None:
        llm = StubLLMProvider(["pick spec_b please"])
        spec_a = _make_spec("A", "spec_a")
        spec_b = _make_spec("B", "spec_b")
        with Tapestry() as t:
            OrchestratorAgent(
                task="solve riddle",
                llm=llm,
                specialists={"spec_a": spec_a, "spec_b": spec_b},
                _config=KnotConfig(id="orch"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        response = run.outputs["orch"]
        assert isinstance(response, AgentResponse)
        assert response.content == "B:solve riddle"

    async def test_rejects_non_llm_provider(self) -> None:
        spec = _make_spec("x", "s")
        k = _make_knot(StubLLMProvider(["s"]), {"s": spec})
        with self.assertRaises(TypeError):
            await k.process(task="ask", llm="bad", specialists={"s": spec})  # type: ignore[arg-type]

    async def test_rejects_empty_specialists(self) -> None:
        llm = StubLLMProvider(["s"])
        spec = _make_spec("x", "s")
        k = _make_knot(llm, {"s": spec})
        with self.assertRaises(ValueError):
            await k.process(task="ask", llm=llm, specialists={})

    async def test_tapestry_run_integration(self) -> None:
        llm = StubLLMProvider(["pick spec_b please"])
        spec_a = _make_spec("A", "spec_a")
        spec_b = _make_spec("B", "spec_b")
        with Tapestry() as t:
            OrchestratorAgent(
                task="solve riddle",
                llm=llm,
                specialists={"spec_a": spec_a, "spec_b": spec_b},
                _config=KnotConfig(id="orch"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["orch"]
        assert isinstance(response, AgentResponse)
        assert response.content == "B:solve riddle"
