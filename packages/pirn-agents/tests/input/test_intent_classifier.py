"""Unit tests for :class:`IntentClassifier`."""

from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.tapestry import Tapestry

from pirn_agents.input.intent_classifier import IntentClassifier
from pirn_agents.types.messaging.agent_message import AgentMessage
from pirn_agents.types.messaging.conversation_payload import ConversationPayload
from tests.conftest import StubLLMProvider


def _make_knot(llm: StubLLMProvider) -> IntentClassifier:
    @knot
    async def _ctx() -> ConversationPayload:
        return ConversationPayload(messages=())

    with Tapestry():
        upstream = _ctx(_config=KnotConfig(id="ctx"))
        return IntentClassifier(
            context=upstream,
            llm=llm,
            intent_categories=("billing", "shipping"),
            _config=KnotConfig(id="ic"),
        )


_CONTEXT = ConversationPayload(
    messages=(AgentMessage(role="user", content="I want a refund"),),
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_classifies_to_exact_match(self) -> None:
        llm = StubLLMProvider(responses=["billing"])
        k = _make_knot(llm)
        result = await k.process(
            context=_CONTEXT,
            llm=llm,
            intent_categories=("billing", "shipping", "support"),
        )
        assert result == "billing"

    async def test_classifies_via_substring(self) -> None:
        llm = StubLLMProvider(responses=["The intent is shipping clearly."])
        k = _make_knot(llm)
        result = await k.process(
            context=_CONTEXT,
            llm=llm,
            intent_categories=("billing", "shipping", "support"),
        )
        assert result == "shipping"

    async def test_raises_when_no_match(self) -> None:
        llm = StubLLMProvider(responses=["totally unrelated"])
        k = _make_knot(llm)
        with self.assertRaises(ValueError):
            await k.process(
                context=_CONTEXT,
                llm=llm,
                intent_categories=("billing", "shipping"),
            )

    async def test_rejects_non_llm_provider(self) -> None:
        llm = StubLLMProvider(responses=["billing"])
        k = _make_knot(llm)
        result = await k(
            {"context": _CONTEXT, "llm": "not-an-llm", "intent_categories": ("billing",)}
        )
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"

    async def test_rejects_empty_intent_list(self) -> None:
        llm = StubLLMProvider(responses=[])
        k = _make_knot(llm)
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                context=_CONTEXT,
                llm=llm,
                intent_categories=(),
            )
