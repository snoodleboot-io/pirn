"""Unit tests for :class:`ResponseFormatter`."""

from __future__ import annotations

import json

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.generation.response_formatter import ResponseFormatter
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.domains.agents.types.tool_call import ToolCall
from pirn.tapestry import Tapestry


@knot
async def emit_response() -> AgentResponse:
    return AgentResponse(
        content="the answer is 42",
        tool_calls=(
            ToolCall(tool_name="calc", arguments={"x": 1}, call_id="c1"),
        ),
        finish_reason="stop",
    )


@pytest.mark.asyncio
class TestProcess:
    async def test_plain_format(self) -> None:
        with Tapestry() as t:
            r = emit_response(_config=KnotConfig(id="r"))
            ResponseFormatter(response=r, _config=KnotConfig(id="f"))
        result = await t.run(RunRequest())
        assert result.outputs["f"] == "the answer is 42"

    async def test_markdown_format(self) -> None:
        with Tapestry() as t:
            r = emit_response(_config=KnotConfig(id="r"))
            ResponseFormatter(
                response=r, format="markdown", _config=KnotConfig(id="f")
            )
        result = await t.run(RunRequest())
        text = result.outputs["f"]
        assert "the answer is 42" in text
        assert "calc" in text

    async def test_json_format(self) -> None:
        with Tapestry() as t:
            r = emit_response(_config=KnotConfig(id="r"))
            ResponseFormatter(
                response=r, format="json", _config=KnotConfig(id="f")
            )
        result = await t.run(RunRequest())
        loaded = json.loads(result.outputs["f"])
        assert loaded["content"] == "the answer is 42"


class TestConstruction:
    def test_rejects_unsupported_format(self) -> None:
        @knot
        async def r() -> AgentResponse:
            return AgentResponse(content="x")

        with Tapestry():
            rr = r(_config=KnotConfig(id="r"))
            with pytest.raises(ValueError, match="format"):
                ResponseFormatter(
                    response=rr, format="xml", _config=KnotConfig(id="f")
                )
