"""``StubTool`` — a configurable, deterministic tool double for tests.

:class:`StubTool` generalises the ad-hoc stubs the agent tests grow locally: a
single :class:`~pirn_agents.tool.Tool` implementation that can act as a plain
sync/async tool, a streaming tool, or a stateful tool, records every
invocation, and lets a test pin its schema, return schema, and permissions. It
ships in the package (not just the test tree) so external tool authors can reuse
it through the testing kit.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from inspect import isawaitable
from typing import Any

from pirn_agents.tool import Tool
from pirn_agents.tool_permissions import ToolPermissions


class StubTool(Tool):
    """A deterministic :class:`Tool` double for exercising the testing kit.

    Configure exactly one behaviour:

    * default / ``result`` — invoking returns ``result``.
    * ``handler`` — invoking returns ``handler(arguments)`` (awaited if it
      returns an awaitable).
    * ``stream_chunks`` — the tool becomes streaming; :meth:`stream` yields the
      chunks and :meth:`invoke` returns them as a list.

    Passing ``state`` makes the tool stateful; the object is exposed via
    :attr:`state` and persists across calls unchanged.
    """

    def __init__(
        self,
        *,
        name: str = "stub_tool",
        description: str = "stub tool",
        parameters_schema: Mapping[str, Any] | None = None,
        return_schema: Mapping[str, Any] | None = None,
        result: Any = "stub-result",
        handler: Callable[[Mapping[str, Any]], Any | Awaitable[Any]] | None = None,
        stream_chunks: Sequence[Any] | None = None,
        state: Any | None = None,
        permissions: ToolPermissions | None = None,
    ) -> None:
        self._name = name
        self._description = description
        self._parameters_schema: dict[str, Any] = (
            dict(parameters_schema)
            if parameters_schema is not None
            else {"type": "object", "properties": {"input": {"type": "string"}}}
        )
        self._return_schema = dict(return_schema) if return_schema is not None else None
        self._result = result
        self._handler = handler
        self._stream_chunks: list[Any] | None = (
            list(stream_chunks) if stream_chunks is not None else None
        )
        self._state = state
        self._permissions = permissions if permissions is not None else ToolPermissions()
        self.invocations: list[Mapping[str, Any]] = []
        self.stream_invocations: list[Mapping[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return self._parameters_schema

    @property
    def return_schema(self) -> Mapping[str, Any] | None:
        """JSON Schema fragment for the return value, or ``None``."""
        return self._return_schema

    @property
    def permissions(self) -> ToolPermissions:
        """Permission / scope metadata for this stub."""
        return self._permissions

    @property
    def streaming(self) -> bool:
        """Return whether this stub streams incremental output."""
        return self._stream_chunks is not None

    @property
    def stateful(self) -> bool:
        """Return whether this stub carries injected state."""
        return self._state is not None

    @property
    def state(self) -> Any | None:
        """Return the injected state object, or ``None``."""
        return self._state

    def stream(self, arguments: Mapping[str, Any]) -> AsyncIterator[Any]:
        """Yield the configured chunks for ``arguments``.

        Raises
        ------
        TypeError
            If this stub was not configured with ``stream_chunks``.
        """
        if self._stream_chunks is None:
            raise TypeError(f"stub tool {self._name!r} is not a streaming tool")
        self.stream_invocations.append(dict(arguments))
        chunks = list(self._stream_chunks)

        async def _aiter() -> AsyncIterator[Any]:
            for chunk in chunks:
                yield chunk

        return _aiter()

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        """Record the call and return the configured result.

        Streaming stubs drain their chunks into a list; ``handler`` stubs call
        the handler (awaiting an awaitable result); otherwise ``result`` is
        returned.
        """
        self.invocations.append(dict(arguments))
        if self._stream_chunks is not None:
            return [chunk async for chunk in self.stream(arguments)]
        if self._handler is not None:
            outcome = self._handler(arguments)
            if isawaitable(outcome):
                return await outcome
            return outcome
        return self._result
