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
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_result import ToolResult


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


class TestParallelToolExecutorDsnScrubbing(unittest.IsolatedAsyncioTestCase):
    """The batch path leaked what the single-call path scrubbed (PIR-733).

    ``ParallelToolExecutor`` captured the raw ``ExceptionRecord``, which does no
    scrubbing, so a tool failing with a DSN in its message wrote live
    credentials into ``ToolResult.error`` and into the record that persists to
    lineage and history. The record carries the message twice — in ``message``
    and again inside ``traceback_text`` — so both are asserted here.
    """

    async def _run_batch(self) -> ToolResult:
        from pirn_agents.agent.parallel_tool_executor import ParallelToolExecutor
        from pirn_agents.tools.toolset import Toolset

        with Tapestry() as t:
            ParallelToolExecutor(
                tool_calls=(ToolCall(call_id="c1", tool_name="raise_tool", arguments={}),),
                toolset=Toolset([_RaisingTool()]),
                _config=KnotConfig(id="batch"),
            )

        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        return result.outputs["batch"][0]

    async def test_dsn_scrubbed_from_error_string(self) -> None:
        outcome = await self._run_batch()
        assert outcome.error is not None
        assert "s3cr3tp4ssw0rd" not in outcome.error

    async def test_dsn_scrubbed_from_the_persisted_exception_record(self) -> None:
        outcome = await self._run_batch()
        assert outcome.exception is not None
        assert "s3cr3tp4ssw0rd" not in outcome.exception.message
        assert "s3cr3tp4ssw0rd" not in outcome.exception.traceback_text
