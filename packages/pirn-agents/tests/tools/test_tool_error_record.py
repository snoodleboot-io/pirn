"""Every tool-invocation path must redact credentials before recording (PIR-733).

`ExceptionRecord` does no scrubbing of its own, and a tool's failure message
routinely carries whatever it was talking to — a DSN, an MCP server URL. Until
this was centralised, one of four paths scrubbed and three did not, so whether
a credential reached lineage and history depended on which call site failed.

These tests pin the redaction at each path rather than only at the helper, so a
new invocation site that forgets it fails here rather than silently leaking.
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_error_record import ToolErrorRecord

_DSN = "postgres://user:s3cr3tp4ssw0rd@host/db"
_SECRET = "s3cr3tp4ssw0rd"


class _RaisingTool(Tool):
    def __init__(self, name: str = "raiser") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "always fails"

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object"}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        raise RuntimeError(f"connect failed: {_DSN}")


class _MultiArgError(Exception):
    """An exception whose constructor takes more than a message.

    Reconstructing this — ``type(exc)(scrubbed)`` — raises ``TypeError``, which
    is why the helper copies the record instead.
    """

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


class TestToolErrorRecord(unittest.TestCase):
    def test_scrubs_both_message_and_traceback(self) -> None:
        """The record carries the message twice; one field is not enough."""
        try:
            raise RuntimeError(f"connect failed: {_DSN}")
        except RuntimeError as exc:
            record = ToolErrorRecord.scrubbed("t", exc)

        assert _SECRET not in record.message
        assert _SECRET not in record.traceback_text
        assert "<redacted>" in record.message

    def test_error_string_is_type_prefixed_and_scrubbed(self) -> None:
        exc = RuntimeError(f"connect failed: {_DSN}")

        message = ToolErrorRecord.scrubbed_message(exc)

        assert message.startswith("RuntimeError: ")
        assert _SECRET not in message

    def test_survives_an_exception_that_cannot_be_reconstructed(self) -> None:
        """Copying the record, not rebuilding the exception, is what makes this work."""
        try:
            raise _MultiArgError(f"connect failed: {_DSN}", 42)
        except _MultiArgError as exc:
            record = ToolErrorRecord.scrubbed("t", exc)

        assert _SECRET not in record.message
        assert record.exc_type == "_MultiArgError"


class TestEveryInvocationPathRedacts(unittest.IsolatedAsyncioTestCase):
    """One test per path, because the defect was inconsistency between them."""

    async def test_tool_invocation(self) -> None:
        from pirn_agents.tools.tool_invocation import ToolInvocation

        with Tapestry() as t:
            ToolInvocation(
                tool=_RaisingTool(),
                call=ToolCall(tool_name="raiser", arguments={}, call_id="c1"),
                _config=KnotConfig(id="inv"),
            )

        outcome = (await t.run(RunRequest())).outputs["inv"]

        assert outcome.error is not None
        assert _SECRET not in outcome.error
        assert outcome.exception is not None
        assert _SECRET not in outcome.exception.message
        assert _SECRET not in outcome.exception.traceback_text

    async def test_parallel_tool_executor(self) -> None:
        from pirn_agents.agent.parallel_tool_executor import ParallelToolExecutor
        from pirn_agents.tools.toolset import Toolset

        with Tapestry() as t:
            ParallelToolExecutor(
                tool_calls=(ToolCall(tool_name="raiser", arguments={}, call_id="c1"),),
                toolset=Toolset([_RaisingTool()]),
                _config=KnotConfig(id="batch"),
            )

        outcome = (await t.run(RunRequest())).outputs["batch"][0]

        assert outcome.exception is not None
        assert _SECRET not in outcome.exception.message
        assert _SECRET not in outcome.exception.traceback_text

    async def test_tool_chain(self) -> None:
        from pirn_agents.specializations.tool_use.tool_chain import ToolChain

        with Tapestry() as t:
            ToolChain(
                initial_call=ToolCall(tool_name="raiser", arguments={}, call_id="c1"),
                tools=(_RaisingTool(),),
                _config=KnotConfig(id="chain"),
            )

        outcome = (await t.run(RunRequest())).outputs["chain"]

        assert outcome.exception is not None
        assert _SECRET not in outcome.exception.message
        assert _SECRET not in outcome.exception.traceback_text
