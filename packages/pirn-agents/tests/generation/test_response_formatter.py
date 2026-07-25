"""Unit tests for :class:`ResponseFormatter`."""

from __future__ import annotations

import json
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.tapestry import Tapestry

from pirn_agents.generation.response_formatter import ResponseFormatter
from pirn_agents.types.agent_response import AgentResponse
from pirn_agents.types.tool_call import ToolCall


def _make_knot() -> ResponseFormatter:
    @knot
    async def _r() -> AgentResponse:
        return AgentResponse(content="x")

    with Tapestry():
        upstream = _r(_config=KnotConfig(id="r"))
        return ResponseFormatter(response=upstream, _config=KnotConfig(id="f"))


_RESPONSE = AgentResponse(
    content="the answer is 42",
    tool_calls=(ToolCall(tool_name="calc", arguments={"x": 1}, call_id="c1"),),
    finish_reason="stop",
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_plain_format(self) -> None:
        k = _make_knot()
        result = await k.process(response=_RESPONSE, format="plain")
        assert result == "the answer is 42"

    async def test_markdown_format(self) -> None:
        k = _make_knot()
        result = await k.process(response=_RESPONSE, format="markdown")
        assert "the answer is 42" in result
        assert "calc" in result

    async def test_json_format(self) -> None:
        k = _make_knot()
        result = await k.process(response=_RESPONSE, format="json")
        loaded = json.loads(result)
        assert loaded["content"] == "the answer is 42"

    async def test_rejects_unsupported_format(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(ValueError, "format"):
            await k.process(response=_RESPONSE, format="xml")

    async def test_rejects_non_agent_response(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(
                response="not a response",  # type: ignore[arg-type]
                format="plain",
            )
