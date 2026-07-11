"""``StreamingTool`` — structural contract for tools that yield partial output.

A streaming tool produces its result incrementally: instead of returning one
value from :meth:`~pirn_agents.tool.Tool.invoke`, it exposes ``stream`` which
returns an async iterator of chunks. This lets a calling agent loop surface
partial output as it arrives (feeding the streaming surface, F23) and reduces
time-to-first-output for long-running tools.

:class:`StreamingTool` is a :func:`~typing.runtime_checkable`
:class:`~typing.Protocol` so both the decorator-built
:class:`~pirn_agents.tool_decorator.FunctionTool` and hand-written tools are
recognised structurally — a tool is streaming when it exposes a truthy
``streaming`` flag and a ``stream`` method. The :func:`supports_streaming`
predicate is the single check callers use, and :func:`collect_stream` is the
convenience drain that materialises a whole stream into a list.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StreamingTool(Protocol):
    """A tool that yields incremental output via :meth:`stream`."""

    @property
    def streaming(self) -> bool:
        """Return ``True`` when this tool streams its output."""
        ...

    def stream(self, arguments: Mapping[str, Any]) -> AsyncIterator[Any]:
        """Return an async iterator yielding partial results for ``arguments``."""
        ...


def supports_streaming(tool: object) -> bool:
    """Return whether ``tool`` streams incremental output.

    A tool qualifies when it satisfies the :class:`StreamingTool` shape *and*
    its ``streaming`` flag is truthy, so a non-streaming tool that merely
    exposes the attributes is correctly excluded.
    """
    return isinstance(tool, StreamingTool) and bool(tool.streaming)


async def collect_stream(tool: StreamingTool, arguments: Mapping[str, Any]) -> list[Any]:
    """Drain ``tool``'s stream for ``arguments`` into a list of chunks."""
    return [chunk async for chunk in tool.stream(arguments)]
