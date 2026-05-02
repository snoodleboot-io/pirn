"""Unit tests for :class:`LLMCall`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.generation.llm_call import LLMCall
from pirn.domains.agents.types.agent_context import AgentContext
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.conftest import StubLLMProvider


@knot
async def emit_context() -> AgentContext:
    return AgentContext(
        messages=(AgentMessage(role="user", content="hi"),),
    )


@pytest.mark.asyncio
class TestProcess:
    async def test_calls_llm_with_wire_messages(self) -> None:
        llm = StubLLMProvider(responses=["hello back"])
        with Tapestry() as t:
            ctx = emit_context(_config=KnotConfig(id="ctx"))
            LLMCall(context=ctx, llm=llm, _config=KnotConfig(id="c"))
        result = await t.run(RunRequest())
        out = result.outputs["c"]
        assert dict(out)["content"] == "hello back"
        assert llm.calls[0][0]["role"] == "user"

    async def test_passes_model_through(self) -> None:
        llm = StubLLMProvider(responses=["x"])
        with Tapestry() as t:
            ctx = emit_context(_config=KnotConfig(id="ctx"))
            LLMCall(
                context=ctx,
                llm=llm,
                model="claude-x",
                _config=KnotConfig(id="c"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["c"]["content"] == "x"


class TestConstruction:
    def test_requires_llm_provider(self) -> None:
        @knot
        async def empty() -> AgentContext:
            return AgentContext(messages=())

        with Tapestry():
            ctx = empty(_config=KnotConfig(id="ctx"))
            with pytest.raises(TypeError, match="LLMProvider"):
                LLMCall(
                    context=ctx,
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="c"),
                )

    def test_rejects_empty_model_string(self) -> None:
        @knot
        async def empty() -> AgentContext:
            return AgentContext(messages=())

        with Tapestry():
            ctx = empty(_config=KnotConfig(id="ctx"))
            llm = StubLLMProvider(responses=[])
            with pytest.raises(ValueError, match="model"):
                LLMCall(
                    context=ctx,
                    llm=llm,
                    model="",
                    _config=KnotConfig(id="c"),
                )
