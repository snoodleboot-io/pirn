"""``BaseTool`` — shared base for the concrete base-library tools.

A :class:`BaseTool` is a thin :class:`~pirn_agents.tool.Tool` subclass that adds
two conveniences every concrete base tool reuses:

* :meth:`as_tool_result` — invoke for a given :class:`~pirn_agents.types.tool_call.ToolCall`
  and wrap the outcome in a typed F1 :class:`~pirn_agents.types.tool_result.ToolResult`
  (timing the call, mapping a raised exception to :attr:`ToolStatus.ERROR`). This
  mirrors the established :class:`~pirn_agents.mcp.mcp_tool.McpTool` pattern so a
  tool round-trips through F1's protocol both under the executor (which wraps the
  raw :meth:`invoke` return) and standalone.
* :meth:`_string_argument` — resolve a required string argument, accepting the
  generic ``"input"`` key as an alias for the tool's primary parameter so the
  same tool works under F1 schema-based calling *and* the text-driven
  :class:`~pirn_agents.specializations.react.react_step_executor.ReActStepExecutor`,
  which passes every action input as ``{"input": ...}``.

Concrete tools still override ``name``/``description``/``parameters_schema`` and
implement :meth:`invoke`.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from pirn_agents.tool import Tool
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_result import ToolResult
from pirn_agents.types.tool_status import ToolStatus


class BaseTool(Tool):
    """A :class:`Tool` with typed-result and argument-resolution helpers."""

    async def as_tool_result(self, call: ToolCall) -> ToolResult:
        """Invoke for ``call`` and return a fully-formed F1 :class:`ToolResult`.

        A raised exception becomes a :attr:`ToolStatus.ERROR` result carrying the
        stringified error rather than propagating, so callers get the same
        terminal shape F1's executor would produce.

        Args:
            call: The originating :class:`ToolCall`; its ``call_id`` is echoed and
                its ``arguments`` are passed to :meth:`invoke`.

        Returns:
            A :class:`ToolResult` with measured ``latency`` and either the tool's
            value (status ``OK``) or the error detail (status ``ERROR``).

        Raises:
            TypeError: If ``call`` is not a :class:`ToolCall`.
        """
        if not isinstance(call, ToolCall):
            raise TypeError(
                f"{type(self).__name__}.as_tool_result: call must be a ToolCall, "
                f"got {type(call).__name__}"
            )
        start = time.perf_counter()
        try:
            value = await self.invoke(call.arguments)
        except Exception as exc:
            return ToolResult(
                call_id=call.call_id,
                result=None,
                status=ToolStatus.ERROR,
                error=str(exc),
                latency=time.perf_counter() - start,
            )
        return ToolResult(
            call_id=call.call_id,
            result=value,
            status=ToolStatus.OK,
            latency=time.perf_counter() - start,
        )

    @staticmethod
    def _require_mapping(tool_name: str, arguments: Mapping[str, Any]) -> None:
        """Raise :class:`TypeError` unless ``arguments`` is a mapping."""
        if not isinstance(arguments, Mapping):
            raise TypeError(
                f"{tool_name}.invoke: arguments must be a Mapping, got {type(arguments).__name__}"
            )

    @staticmethod
    def _string_argument(
        tool_name: str,
        arguments: Mapping[str, Any],
        name: str,
        *,
        allow_empty: bool = False,
    ) -> str:
        """Return the string argument ``name``, falling back to ``"input"``.

        The ``"input"`` alias lets a single-string tool be driven by the text
        ReAct loop (which supplies ``{"input": ...}``) as well as by schema-based
        F1 tool calls that use the canonical parameter name.

        Args:
            tool_name: Owning tool name, used in error messages.
            arguments: The invocation argument mapping.
            name: The canonical parameter key to read.
            allow_empty: When ``False`` (default), an empty string is rejected.

        Raises:
            ValueError: If neither ``name`` nor ``"input"`` yields a string (or the
                value is empty and ``allow_empty`` is ``False``).
        """
        value = arguments.get(name)
        if value is None:
            value = arguments.get("input")
        if not isinstance(value, str) or (not allow_empty and not value):
            raise ValueError(
                f"{tool_name}.invoke: {name!r} must be a non-empty string, got {value!r}"
            )
        return value
