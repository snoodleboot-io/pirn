"""Unit tests for :class:`LLMCall`."""

from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.tapestry import Tapestry

from pirn_agents.generation.llm_call import LLMCall
from pirn_agents.types.messaging.agent_message import AgentMessage
from pirn_agents.types.messaging.conversation_payload import ConversationPayload
from tests.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> LLMCall:
    @KnotFactory.knot
    async def _ctx() -> ConversationPayload:
        return ConversationPayload(messages=())

    with Tapestry():
        upstream = _ctx(_config=KnotConfig(id="ctx"))
        return LLMCall(context=upstream, llm=llm, _config=KnotConfig(id="c"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_calls_llm_with_wire_messages(self) -> None:
        llm = StubLLMProvider(responses=["hello back"])
        k = _make_knot(llm)
        context = ConversationPayload(messages=(AgentMessage(role="user", content="hi"),))
        out = await k.process(context=context, llm=llm, model=None)
        assert dict(out)["content"] == "hello back"
        assert llm.calls[0][0]["role"] == "user"

    async def test_passes_model_through(self) -> None:
        llm = StubLLMProvider(responses=["x"])
        k = _make_knot(llm)
        context = ConversationPayload(messages=(AgentMessage(role="user", content="hi"),))
        out = await k.process(context=context, llm=llm, model="claude-x")
        assert out["content"] == "x"

    async def test_rejects_non_agent_context(self) -> None:
        llm = StubLLMProvider(responses=["x"])
        k = _make_knot(llm)
        result = await k({"context": "not a context", "llm": llm, "model": None})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(responses=["x"])
        k = _make_knot(llm)
        context = ConversationPayload(messages=())
        result = await k({"context": context, "llm": "bad", "model": None})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"

    async def test_rejects_empty_model_string(self) -> None:
        llm = StubLLMProvider(responses=["x"])
        k = _make_knot(llm)
        context = ConversationPayload(messages=())
        with self.assertRaisesRegex(ValueError, "model"):
            await k.process(context=context, llm=llm, model="")
