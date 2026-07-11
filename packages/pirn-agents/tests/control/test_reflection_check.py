"""Unit tests for :class:`ReflectionCheck`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.tapestry import Tapestry

from pirn_agents.control.reflection_check import ReflectionCheck
from pirn_agents.types.agent_response import AgentResponse
from tests.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> ReflectionCheck:
    @knot
    async def _r() -> AgentResponse:
        return AgentResponse(content="x")

    with Tapestry():
        upstream = _r(_config=KnotConfig(id="r"))
        return ReflectionCheck(
            response=upstream,
            llm=llm,
            _config=KnotConfig(id="g"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_yes_means_iterate(self) -> None:
        llm = StubLLMProvider(responses=["yes"])
        k = _make_knot(llm)
        result = await k.process(
            response=AgentResponse(content="some answer"),
            llm=llm,
        )
        assert result is True

    async def test_no_means_terminate(self) -> None:
        llm = StubLLMProvider(responses=["no, looks fine"])
        k = _make_knot(llm)
        result = await k.process(
            response=AgentResponse(content="some answer"),
            llm=llm,
        )
        assert result is False

    async def test_rejects_non_agent_response(self) -> None:
        llm = StubLLMProvider(responses=["yes"])
        k = _make_knot(llm)
        with self.assertRaises(TypeError):
            await k.process(
                response="not a response",  # type: ignore[arg-type]
                llm=llm,
            )

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(responses=["yes"])
        k = _make_knot(llm)
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            await k.process(
                response=AgentResponse(content="x"),
                llm="bad",  # type: ignore[arg-type]
            )
