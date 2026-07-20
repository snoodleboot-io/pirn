"""ToolExecutor scrubs DSN credentials from error strings (M-5).

Native pirn-agents test for :class:`ToolExecutor`'s error handling. (Previously
lived under ``pirn-core/tests`` as a cross-domain test; relocated here since it
exercises pirn-agents code only — pirn-core is imported as the run harness,
never tested.)
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.planning.tool_executor import ToolExecutor
from pirn_agents.tool import Tool
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_result import ToolResult


class _RaisingTool(Tool):
    @property
    def name(self) -> str:
        return "raise_tool"

    @property
    def description(self) -> str:
        return "always raises with a DSN-containing message"

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        raise RuntimeError("failed: postgres://user:s3cr3tp4ssw0rd@host/db")


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
