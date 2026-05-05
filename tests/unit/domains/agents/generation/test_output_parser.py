"""Unit tests for :class:`OutputParser`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.generation.output_parser import OutputParser
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


@knot
async def emit_simple_response() -> dict:
    return {"content": "all good", "stop_reason": "stop"}


@knot
async def emit_blocks_response() -> dict:
    return {
        "content": [
            {"type": "text", "text": "hello "},
            {"type": "text", "text": "world"},
            {
                "type": "tool_use",
                "id": "call-1",
                "name": "search",
                "input": {"q": "x"},
            },
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 7, "output_tokens": 3},
    }


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_parses_string_content(self) -> None:
        with Tapestry() as t:
            raw = emit_simple_response(_config=KnotConfig(id="raw"))
            OutputParser(response=raw, _config=KnotConfig(id="p"))
        result = await t.run(RunRequest())
        response: AgentResponse = result.outputs["p"]
        assert response.content == "all good"
        assert response.finish_reason == "stop"
        assert response.tool_calls == ()

    async def test_parses_block_content_with_tool_use(self) -> None:
        with Tapestry() as t:
            raw = emit_blocks_response(_config=KnotConfig(id="raw"))
            OutputParser(response=raw, _config=KnotConfig(id="p"))
        result = await t.run(RunRequest())
        response: AgentResponse = result.outputs["p"]
        assert response.content == "hello world"
        assert response.finish_reason == "tool_use"
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool_name == "search"
        assert response.usage["input_tokens"] == 7

    async def test_rejects_unrecognised_shape(self) -> None:
        @knot
        async def bad() -> dict:
            return {"foo": "bar"}

        with Tapestry() as t:
            raw = bad(_config=KnotConfig(id="raw"))
            OutputParser(response=raw, _config=KnotConfig(id="p"))
        result = await t.run(RunRequest())
        assert "p" not in result.outputs
