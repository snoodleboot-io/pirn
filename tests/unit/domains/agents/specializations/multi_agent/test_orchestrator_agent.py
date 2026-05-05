"""Tests for :class:`OrchestratorAgent`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.multi_agent.orchestrator_agent import (
    OrchestratorAgent,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class StubSpecialist(SubTapestry):
    """SubTapestry double that emits a fixed AgentResponse for any task."""

    def __init__(self, *, task: Any = "", _config: KnotConfig, reply: str = "specialist-reply", **kwargs: Any,) -> None:
        self._reply = reply
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str, **_: Any) -> AgentResponse:
        return AgentResponse(
            content=f"{self._reply}:{task}",
            finish_reason="stop",
        )


class TestOrchestratorAgentConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_llm_provider(self) -> None:
        with Tapestry():
            spec = StubSpecialist(_config=KnotConfig(id="spec_a"))
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            with Tapestry():
                OrchestratorAgent(
                    task="ask",
                    llm="not-a-provider",  # type: ignore[arg-type]
                    specialists={"spec_a": spec},
                    _config=KnotConfig(id="orch"),
                )

    async def test_rejects_empty_specialists(self) -> None:
        llm = StubLLMProvider(["spec_a"])
        with self.assertRaisesRegex(ValueError, "specialists"):
            with Tapestry():
                OrchestratorAgent(
                    task="ask",
                    llm=llm,
                    specialists={},
                    _config=KnotConfig(id="orch"),
                )


class TestOrchestratorAgentHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_routes_to_named_specialist(self) -> None:
        llm = StubLLMProvider(["pick spec_b please"])
        with Tapestry():
            spec_a = StubSpecialist(
                _config=KnotConfig(id="spec_a"),
                reply="A",
            )
            spec_b = StubSpecialist(
                _config=KnotConfig(id="spec_b"),
                reply="B",
            )
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
