"""Unit tests for :class:`OutputParser`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn_agents.generation.output_parser import OutputParser
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


def _make_knot() -> OutputParser:
    @knot
    async def _r() -> dict:
        return {"content": "x"}

    with Tapestry():
        upstream = _r(_config=KnotConfig(id="raw"))
        return OutputParser(response=upstream, _config=KnotConfig(id="p"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_parses_string_content(self) -> None:
        k = _make_knot()
        response: AgentResponse = await k.process(
            response={"content": "all good", "stop_reason": "stop"},
        )
        assert response.content == "all good"
        assert response.finish_reason == "stop"
        assert response.tool_calls == ()

    async def test_parses_block_content_with_tool_use(self) -> None:
        k = _make_knot()
        response: AgentResponse = await k.process(
            response={
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
        )
        assert response.content == "hello world"
        assert response.finish_reason == "tool_use"
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool_name == "search"
        assert response.usage["input_tokens"] == 7

    async def test_rejects_unrecognised_shape(self) -> None:
        k = _make_knot()
        with self.assertRaises(ValueError):
            await k.process(response={"foo": "bar"})

    async def test_rejects_non_mapping(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(response="not a mapping")  # type: ignore[arg-type]
