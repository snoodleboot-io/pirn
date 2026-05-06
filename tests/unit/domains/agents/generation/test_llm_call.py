"""Unit tests for :class:`LLMCall`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.agents.generation.llm_call import LLMCall
from pirn.domains.agents.types.agent_context import AgentContext
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> LLMCall:
    @knot
    async def _ctx() -> AgentContext:
        return AgentContext(messages=())

    with Tapestry():
        upstream = _ctx(_config=KnotConfig(id="ctx"))
        return LLMCall(context=upstream, llm=llm, _config=KnotConfig(id="c"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_calls_llm_with_wire_messages(self) -> None:
        llm = StubLLMProvider(responses=["hello back"])
        k = _make_knot(llm)
        context = AgentContext(messages=(AgentMessage(role="user", content="hi"),))
        out = await k.process(context=context, llm=llm, model=None)
        assert dict(out)["content"] == "hello back"
        assert llm.calls[0][0]["role"] == "user"

    async def test_passes_model_through(self) -> None:
        llm = StubLLMProvider(responses=["x"])
        k = _make_knot(llm)
        context = AgentContext(messages=(AgentMessage(role="user", content="hi"),))
        out = await k.process(context=context, llm=llm, model="claude-x")
        assert out["content"] == "x"

    async def test_rejects_non_agent_context(self) -> None:
        llm = StubLLMProvider(responses=["x"])
        k = _make_knot(llm)
        with self.assertRaises(TypeError):
            await k.process(
                context="not a context",  # type: ignore[arg-type]
                llm=llm,
                model=None,
            )

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(responses=["x"])
        k = _make_knot(llm)
        context = AgentContext(messages=())
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            await k.process(
                context=context,
                llm="bad",  # type: ignore[arg-type]
                model=None,
            )

    async def test_rejects_empty_model_string(self) -> None:
        llm = StubLLMProvider(responses=["x"])
        k = _make_knot(llm)
        context = AgentContext(messages=())
        with self.assertRaisesRegex(ValueError, "model"):
            await k.process(context=context, llm=llm, model="")
