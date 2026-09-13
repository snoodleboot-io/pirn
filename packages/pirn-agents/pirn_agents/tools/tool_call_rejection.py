"""``ToolCallRejection`` — a call that could not be dispatched, as a graph node.

A fan-out over tool calls wires one knot per call and lets the engine record
each outcome.  A call that names a tool the toolset does not hold, or whose
arguments the declaration refuses, has no tool knot to wire — but it still
needs a node, so its ``Err`` sits beside its siblings' results in lineage
instead of aborting the executor that built the graph (ADR agents-speaks-core,
WS1).  This knot is that node: its ``process()`` raises the error it was
given, and the engine records the ``Err`` under the call's id like any other
failed knot.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.tools.tool_call import ToolCall


class ToolCallRejection(Knot):
    """Record, as the call's own ``Err``, why a :class:`ToolCall` could not be dispatched."""

    def __init__(
        self,
        *,
        call: Knot | ToolCall,
        error: Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        """Wire the rejected call.

        Args:
            call: The call that could not be dispatched.
            error: The exception describing why — a
                :class:`~pirn_agents.exceptions.tool_not_found_error.ToolNotFoundError`
                or a
                :class:`~pirn_agents.exceptions.tool_argument_validation_error.ToolArgumentValidationError`.
                Typed ``Any`` because an exception instance has no pydantic
                schema for core's eager adapter build.
            _config: Framework metadata; ``id`` is the call's knot id.
        """
        super().__init__(call=call, error=error, _config=_config, **kwargs)

    async def process(self, call: ToolCall, error: Any, **_: Any) -> Any:
        """Raise ``error`` so the engine records this call as ``Err``.

        Args:
            call: The rejected call (kept as an input so lineage names it).
            error: The exception to raise.

        Raises:
            BaseException: Always — ``error`` itself when it is an exception,
                else a ``TypeError`` naming the call.
        """
        if isinstance(error, BaseException):
            raise error
        raise TypeError(f"tool call {call.call_id!r} rejected: {error!r}")
