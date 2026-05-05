"""Unit tests for :class:`_LLMCallKnot`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.structured_output._llm_call_knot import (
    _LLMCallKnot,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestLLMCallKnotProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_llm_text(self) -> None:
        llm = StubLLMProvider(["hello from llm"])
        with Tapestry() as t:
            _LLMCallKnot(
                prompt="say hello",
                llm=llm,
                _config=KnotConfig(id="lck"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["lck"] == "hello from llm"

    async def test_prompt_sent_to_llm(self) -> None:
        llm = StubLLMProvider(["response"])
        with Tapestry() as t:
            _LLMCallKnot(
                prompt="my custom prompt",
                llm=llm,
                _config=KnotConfig(id="lck"),
            )
        await t.run(RunRequest())
        assert llm.calls[0][-1]["content"] == "my custom prompt"
