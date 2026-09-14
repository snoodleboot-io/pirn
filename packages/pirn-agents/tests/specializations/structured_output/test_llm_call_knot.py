"""Unit tests for :class:`LLMCallKnot`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.structured_output.llm_call_knot import (
    LLMCallKnot,
)
from tests.specializations.conftest import StubLLMProvider


class TestLLMCallKnotProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_llm_text(self) -> None:
        llm = StubLLMProvider(["hello from llm"])
        with Tapestry() as t:
            LLMCallKnot(
                prompt="say hello",
                llm=llm,
                _config=KnotConfig(id="lck"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["lck"] == "hello from llm"

    async def test_prompt_sent_to_llm(self) -> None:
        llm = StubLLMProvider(["response"])
        with Tapestry() as t:
            LLMCallKnot(
                prompt="my custom prompt",
                llm=llm,
                _config=KnotConfig(id="lck"),
            )
        await t.run(RunRequest())
        assert llm.calls[0][-1]["content"] == "my custom prompt"


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_returns_llm_text(self) -> None:
        # AgentCallRecorder.record() (ADR agents-speaks-core WS5b) reads
        # self.knot_id, which requires a fully-bootstrapped knot -- construct
        # normally rather than via __new__ + a bare _config attribute.
        llm = StubLLMProvider(["direct result"])
        with Tapestry():
            k = LLMCallKnot(prompt="ask something", llm=llm, _config=KnotConfig(id="x"))
        result = await k.process(prompt="ask something", llm=llm)
        assert isinstance(result, str)
        assert result == "direct result"
