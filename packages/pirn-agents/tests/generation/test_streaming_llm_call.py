"""Unit tests for :class:`StreamingLLMCall`."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.tapestry import Tapestry

from pirn_agents.generation.streaming_llm_call import StreamingLLMCall
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.llm.stream_delta import StreamDelta
from pirn_agents.types.messaging.agent_context import AgentContext
from pirn_agents.types.messaging.agent_message import AgentMessage
from tests.conftest import StubLLMProvider


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
        context = AgentContext(messages=(AgentMessage(role="user", content="stream"),))
        stream = await k.process(context=context, llm=llm, model=None)
        chunks: list[str] = []
        async for chunk in stream:
            chunks.append(chunk.content)
        assert chunks == ["a", "b", "c"]

    async def test_streams_from_a_provider_written_as_an_async_generator(self) -> None:
        """The knot must work against the shape every real provider has (PIR-833).

        ``BaseLLMProvider.stream_chat`` — and so every shipped provider — is an
        async generator: calling it returns the iterator, it is never awaited.
        The knot used to ``await`` the call, which raises ``TypeError`` against
        exactly that shape; only doubles that returned an iterator out of a
        coroutine kept the tests green.
        """

        class GeneratorProvider(LLMProvider):
            def stream_chat(  # type: ignore[override]
                self,
                messages: Sequence[Mapping[str, Any]],
                *,
                model: str | None = None,
                max_tokens: int | None = None,
                temperature: float | None = None,
            ) -> AsyncIterator[StreamDelta]:
                async def _aiter() -> AsyncIterator[StreamDelta]:
                    for text in ("x", "y"):
                        yield StreamDelta(content=text)

                return _aiter()

        provider = GeneratorProvider()
        k = _make_knot(StubLLMProvider(responses=["ignored"]))
        context = AgentContext(messages=(AgentMessage(role="user", content="stream"),))
        stream = await k.process(context=context, llm=provider, model=None)
        assert [delta.content async for delta in stream] == ["x", "y"]

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
