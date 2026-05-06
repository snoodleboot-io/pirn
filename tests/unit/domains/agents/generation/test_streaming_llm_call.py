"""Unit tests for :class:`StreamingLLMCall`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.agents.generation.streaming_llm_call import StreamingLLMCall
from pirn.domains.agents.types.agent_context import AgentContext
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> StreamingLLMCall:
    @knot
    async def _ctx() -> AgentContext:
        return AgentContext(messages=())

    with Tapestry():
        upstream = _ctx(_config=KnotConfig(id="ctx"))
        return StreamingLLMCall(
            context=upstream,
            llm=llm,
            _config=KnotConfig(id="s"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_async_iterator(self) -> None:
        llm = StubLLMProvider(responses=["a", "b", "c"])
        k = _make_knot(llm)
        context = AgentContext(
            messages=(AgentMessage(role="user", content="stream"),)
        )
        stream = await k.process(context=context, llm=llm, model=None)
        chunks: list[str] = []
        async for chunk in stream:
            chunks.append(chunk["content"])
        assert chunks == ["a", "b", "c"]

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
