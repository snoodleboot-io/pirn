"""Unit tests for :class:`FormatCoercer`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.structured_output.format_coercer import (
    FormatCoercer,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestFormatCoercerConstruction(unittest.TestCase):
    def test_rejects_non_llm_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            with Tapestry():
                FormatCoercer(
                    response=AgentResponse(content="x", finish_reason="stop"),
                    llm="bad",  # type: ignore[arg-type]
                    target_format="json",
                    _config=KnotConfig(id="fc"),
                )

    def test_rejects_unsupported_format(self) -> None:
        with self.assertRaisesRegex(ValueError, "target_format"):
            with Tapestry():
                FormatCoercer(
                    response=AgentResponse(content="x", finish_reason="stop"),
                    llm=StubLLMProvider([]),
                    target_format="xml",
                    _config=KnotConfig(id="fc"),
                )


class TestFormatCoercerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_original_when_already_json(self) -> None:
        llm = StubLLMProvider(["rewritten"])
        response = AgentResponse(content='{"key": "value"}', finish_reason="stop")
        with Tapestry() as t:
            FormatCoercer(
                response=response,
                llm=llm,
                target_format="json",
                _config=KnotConfig(id="fc"),
            )
        result = await t.run(RunRequest())
        # should be original (no LLM call)
        assert result.outputs["fc"] is response
        assert len(llm.calls) == 0

    async def test_rewrites_non_json_content(self) -> None:
        llm = StubLLMProvider(['{"x": 1}'])
        response = AgentResponse(content="plain text", finish_reason="stop")
        with Tapestry() as t:
            FormatCoercer(
                response=response,
                llm=llm,
                target_format="json",
                _config=KnotConfig(id="fc"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["fc"]
        assert out.content == '{"x": 1}'

    async def test_rejects_non_agent_response(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry():
            with self.assertRaises(TypeError):
                FormatCoercer(
                    response="not-a-response",  # type: ignore[arg-type]
                    llm=llm,
                    target_format="json",
                    _config=KnotConfig(id="fc"),
                )
