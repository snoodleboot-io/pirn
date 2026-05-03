"""Unit tests for :class:`ReflectionCheck`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.control.reflection_check import ReflectionCheck
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.conftest import StubLLMProvider


@knot
async def emit_response() -> AgentResponse:
    return AgentResponse(content="some answer")


@pytest.mark.asyncio
class TestProcess:
    async def test_yes_means_iterate(self) -> None:
        llm = StubLLMProvider(responses=["yes"])
        with Tapestry() as t:
            r = emit_response(_config=KnotConfig(id="r"))
            ReflectionCheck(response=r, llm=llm, _config=KnotConfig(id="g"))
        result = await t.run(RunRequest())
        assert result.outputs["g"] is True

    async def test_no_means_terminate(self) -> None:
        llm = StubLLMProvider(responses=["no, looks fine"])
        with Tapestry() as t:
            r = emit_response(_config=KnotConfig(id="r"))
            ReflectionCheck(response=r, llm=llm, _config=KnotConfig(id="g"))
        result = await t.run(RunRequest())
        assert result.outputs["g"] is False


class TestConstruction:
    def test_requires_llm_provider(self) -> None:
        @knot
        async def r() -> AgentResponse:
            return AgentResponse(content="x")

        with Tapestry():
            rr = r(_config=KnotConfig(id="r"))
            with pytest.raises(TypeError, match="LLMProvider"):
                ReflectionCheck(
                    response=rr,
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="g"),
                )
