"""Unit tests for :class:`FormatCoercer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.specializations.structured_output.format_coercer import (
    FormatCoercer,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry

from tests.specializations.conftest import StubLLMProvider


class TestFormatCoercerValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_llm_provider(self) -> None:
        knot = FormatCoercer.__new__(FormatCoercer)
        with self.assertRaisesRegex(TypeError, "LLMProvider"):
            await knot.process(
                response=AgentResponse(content="x", finish_reason="stop"),
                llm="bad",  # type: ignore[arg-type]
                target_format="json",
            )

    async def test_rejects_unsupported_format(self) -> None:
        knot = FormatCoercer.__new__(FormatCoercer)
        with self.assertRaisesRegex(ValueError, "target_format"):
            await knot.process(
                response=AgentResponse(content="x", finish_reason="stop"),
                llm=StubLLMProvider([]),
                target_format="xml",
            )

    async def test_rejects_non_agent_response(self) -> None:
        knot = FormatCoercer.__new__(FormatCoercer)
        with self.assertRaises(TypeError):
            await knot.process(
                response="not-a-response",  # type: ignore[arg-type]
                llm=StubLLMProvider(["x"]),
                target_format="json",
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
