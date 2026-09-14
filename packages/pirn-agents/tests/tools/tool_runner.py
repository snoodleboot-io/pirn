"""``ToolRunner`` — drive one call of a tool capability in a unit test.

A tool is a ``Knot`` class since the ADR "agents speaks core" (WS1); a
capability is a :class:`~pirn_agents.tools.tool_factory.ToolFactory`.  These
helpers give tests the three shapes they need without a tapestry each time:

* :meth:`value` — construct the call knot and run its ``process()`` directly
  with the resolved inputs, so the tool's own exceptions propagate unchanged
  (the sanctioned standalone path for a knot body);
* :meth:`view` — run the call outside the engine and return the
  :class:`ToolResult` view of its ``Result``;
* :meth:`run` — run the call in a real tapestry and return the ``RunResult``
  so lineage can be asserted.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.err import Err
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.managers.exception_record import ExceptionRecord
from pirn.tapestry import Tapestry

from pirn_agents.exceptions.tool_argument_validation_error import (
    ToolArgumentValidationError,
)
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_call_codec import ToolCallCodec
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_result import ToolResult


class ToolRunner:
    """Test drivers over :meth:`ToolFactory.for_call`."""

    @staticmethod
    async def value(tool: Any, arguments: Mapping[str, Any], *, call_id: str = "test") -> Any:
        """Run the call's ``process()`` directly and return the tool's value."""
        if not isinstance(arguments, Mapping):
            raise TypeError(f"arguments must be a Mapping, got {type(arguments).__name__}")
        factory = ToolFactory.of(tool)
        call = ToolCall(tool_name=factory.name, arguments=dict(arguments), call_id=call_id)
        knot = factory.for_call(call)
        return await knot.process(**knot.config_values)

    @staticmethod
    async def view(tool: Any, call: ToolCall) -> ToolResult:
        """Run the call in a fresh tapestry and return its ``ToolResult`` view (with lineage)."""
        if not isinstance(call, ToolCall):
            raise TypeError(f"call must be a ToolCall, got {type(call).__name__}")
        factory = ToolFactory.of(tool)
        with Tapestry() as tapestry:
            try:
                factory.for_call(call)
            except ToolArgumentValidationError as exc:
                return ToolResult(
                    call_id=call.call_id,
                    outcome=Err(record=ExceptionRecord.for_knot(call.call_id, exc)),
                )
        run = await tapestry.run(RunRequest())
        outcome = ToolCallCodec.outcomes_of(run, [call])[call.call_id]
        return ToolCallCodec.views({call.call_id: outcome}, lineage=run.lineage)[0]

    @staticmethod
    async def run(tool: Any, arguments: Mapping[str, Any], *, call_id: str = "test") -> RunResult:
        """Run the call in a fresh tapestry and return the ``RunResult``."""
        factory = ToolFactory.of(tool)
        call = ToolCall(tool_name=factory.name, arguments=dict(arguments), call_id=call_id)
        with Tapestry() as tapestry:
            factory.for_call(call)
        return await tapestry.run(RunRequest())
