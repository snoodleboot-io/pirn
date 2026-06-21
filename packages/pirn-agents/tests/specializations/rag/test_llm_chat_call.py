"""Unit tests for :class:`LLMChatCall`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.rag.llm_chat_call import LLMChatCall
from pirn.tapestry import Tapestry

from tests.specializations.conftest import StubLLMProvider


class TestLLMChatCallConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_llm_provider(self) -> None:
        with Tapestry():
            k = LLMChatCall.__new__(LLMChatCall)
            object.__setattr__(k, "_config", KnotConfig(id="lcc"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(prompt="hello", llm="bad")  # type: ignore[arg-type]

    async def test_rejects_non_positive_max_tokens(self) -> None:
        llm = StubLLMProvider([])
        with Tapestry():
            k = LLMChatCall.__new__(LLMChatCall)
            object.__setattr__(k, "_config", KnotConfig(id="lcc"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(prompt="hello", llm=llm, max_tokens=0)


class TestLLMChatCallProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_llm_text(self) -> None:
        llm = StubLLMProvider(["The answer is 42."])
        with Tapestry() as t:
            LLMChatCall(
                prompt="What is the answer?",
                llm=llm,
                _config=KnotConfig(id="lcc"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["lcc"] == "The answer is 42."

    async def test_includes_system_message_when_set(self) -> None:
        llm = StubLLMProvider(["answer"])
        with Tapestry() as t:
            LLMChatCall(
                prompt="prompt",
                llm=llm,
                system="You are helpful.",
                _config=KnotConfig(id="lcc"),
            )
        await t.run(RunRequest())
        messages = llm.calls[0]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful."

    async def test_rejects_non_string_prompt(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry():
            with self.assertRaises(TypeError):
                LLMChatCall(
                    prompt=42,  # type: ignore[arg-type]
                    llm=llm,
                    _config=KnotConfig(id="lcc"),
                )
