"""Unit tests for :class:`IntentClassifier`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.input.intent_classifier import IntentClassifier
from pirn.domains.agents.types.agent_context import AgentContext
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.conftest import StubLLMProvider


@knot
async def emit_context() -> AgentContext:
    return AgentContext(
        messages=(AgentMessage(role="user", content="I want a refund"),),
    )


@pytest.mark.asyncio
class TestProcess:
    async def test_classifies_to_exact_match(self) -> None:
        llm = StubLLMProvider(responses=["billing"])
        with Tapestry() as t:
            ctx = emit_context(_config=KnotConfig(id="ctx"))
            IntentClassifier(
                context=ctx,
                llm=llm,
                intent_categories=("billing", "shipping", "support"),
                _config=KnotConfig(id="ic"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["ic"] == "billing"

    async def test_classifies_via_substring(self) -> None:
        llm = StubLLMProvider(responses=["The intent is shipping clearly."])
        with Tapestry() as t:
            ctx = emit_context(_config=KnotConfig(id="ctx"))
            IntentClassifier(
                context=ctx,
                llm=llm,
                intent_categories=("billing", "shipping", "support"),
                _config=KnotConfig(id="ic"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["ic"] == "shipping"

    async def test_raises_when_no_match(self) -> None:
        llm = StubLLMProvider(responses=["totally unrelated"])
        with Tapestry() as t:
            ctx = emit_context(_config=KnotConfig(id="ctx"))
            IntentClassifier(
                context=ctx,
                llm=llm,
                intent_categories=("billing", "shipping"),
                _config=KnotConfig(id="ic"),
            )
        result = await t.run(RunRequest())
        assert "ic" not in result.outputs


class TestConstruction:
    def test_requires_llm_provider(self) -> None:
        @knot
        async def empty() -> AgentContext:
            return AgentContext(messages=())

        with Tapestry():
            ctx = empty(_config=KnotConfig(id="ctx"))
            with pytest.raises(TypeError, match="LLMProvider"):
                IntentClassifier(
                    context=ctx,
                    llm="not-an-llm",  # type: ignore[arg-type]
                    intent_categories=("a",),
                    _config=KnotConfig(id="ic"),
                )

    def test_rejects_empty_intent_list(self) -> None:
        @knot
        async def empty() -> AgentContext:
            return AgentContext(messages=())

        with Tapestry():
            ctx = empty(_config=KnotConfig(id="ctx"))
            llm = StubLLMProvider(responses=[])
            with pytest.raises(ValueError, match="non-empty"):
                IntentClassifier(
                    context=ctx,
                    llm=llm,
                    intent_categories=(),
                    _config=KnotConfig(id="ic"),
                )
