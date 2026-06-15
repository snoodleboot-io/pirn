"""Security tests: M-5 — ToolExecutor scrubs DSN credentials from error strings."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn_agents.tool import Tool
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_result import ToolResult
from pirn_agents.planning.tool_executor import ToolExecutor
from pirn.tapestry import Tapestry


class _RaisingTool(Tool):
    name = "raise_tool"
    description = "always raises with a DSN-containing message"

    async def invoke(self, arguments: dict) -> object:
        raise RuntimeError("failed: postgres://user:s3cr3tp4ssw0rd@host/db")


class _CallSource:
    pass


class TestToolExecutorDsnScrubbing(unittest.IsolatedAsyncioTestCase):
    async def test_dsn_credentials_scrubbed_from_error(self) -> None:
        @knot
        async def call_source() -> ToolCall:
            return ToolCall(call_id="c1", tool_name="raise_tool", arguments={})

        with Tapestry() as t:
            call_knot = call_source(_config=KnotConfig(id="call"))
            ToolExecutor(
                call=call_knot,
                tools=[_RaisingTool()],
                _config=KnotConfig(id="exec"),
            )

        result = await t.run(RunRequest())
        tool_result: ToolResult = result.outputs["exec"]
        assert tool_result.error is not None
        assert "s3cr3tp4ssw0rd" not in tool_result.error
        assert "<redacted>" in tool_result.error

    async def test_unknown_tool_produces_safe_error(self) -> None:
        @knot
        async def call_source() -> ToolCall:
            return ToolCall(call_id="c2", tool_name="nonexistent", arguments={})

        with Tapestry() as t:
            call_knot = call_source(_config=KnotConfig(id="call"))
            ToolExecutor(
                call=call_knot,
                tools=[_RaisingTool()],
                _config=KnotConfig(id="exec"),
            )

        result = await t.run(RunRequest())
        tool_result: ToolResult = result.outputs["exec"]
        assert tool_result.error is not None
        assert "nonexistent" in tool_result.error
