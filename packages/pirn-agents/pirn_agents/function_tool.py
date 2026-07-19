"""``FunctionTool`` — the concrete :class:`Tool` produced by the ``@tool`` decorator.

Wraps a plain Python function (sync, async, or async-generator) with a
pre-compiled name / description / parameters schema and optional argument
validator, streaming flag, and injected state. It is constructed by the
:func:`~pirn_agents.tool_decorator.tool` decorator — not instantiated directly.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Mapping
from typing import Any

from pirn_agents.tool import Tool
from pirn_agents.tool_permissions import ToolPermissions


class FunctionTool(Tool):
    """A :class:`Tool` backed by a plain Python function.

    Produced by the :func:`~pirn_agents.tool_decorator.tool` decorator. Do not
    instantiate directly.
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        *,
        name: str,
        description: str,
        parameters_schema: Mapping[str, Any],
        is_async: bool,
        return_schema: Mapping[str, Any] | None = None,
        permissions: ToolPermissions | None = None,
        args_validator: Callable[[Mapping[str, Any]], Any] | None = None,
        is_streaming: bool = False,
        state: Any | None = None,
        is_stateful: bool = False,
    ) -> None:
        self._fn = fn
        self._name = name
        self._description = description
        self._parameters_schema = dict(parameters_schema)
        self._is_async = is_async
        self._return_schema = dict(return_schema) if return_schema is not None else None
        self._permissions = permissions if permissions is not None else ToolPermissions()
        self._args_validator = args_validator
        self._is_streaming = is_streaming
        self._state = state
        self._is_stateful = is_stateful

    @property
    def name(self) -> str:
        """Stable identifier derived from the wrapped function's ``__name__``."""
        return self._name

    @property
    def description(self) -> str:
        """First docstring paragraph of the wrapped function, or the function name."""
        return self._description

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """JSON Schema object describing the tool's arguments."""
        return self._parameters_schema

    @property
    def return_schema(self) -> Mapping[str, Any] | None:
        """JSON Schema fragment for the return value, or ``None`` if untyped."""
        return self._return_schema

    @property
    def permissions(self) -> ToolPermissions:
        """Permission / scope metadata attached to this tool."""
        return self._permissions

    @property
    def streaming(self) -> bool:
        """Return whether this tool yields incremental output via :meth:`stream`."""
        return self._is_streaming

    @property
    def stateful(self) -> bool:
        """Return whether this tool carries injected state across calls."""
        return self._is_stateful

    @property
    def state(self) -> Any | None:
        """Return the injected state/resource object, or ``None``."""
        return self._state

    def _prepare_call(self, arguments: Mapping[str, Any]) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """Build the positional/keyword arguments for the wrapped function.

        When an ``args_model`` is configured the mapping is validated/coerced
        and the validated object is passed positionally; otherwise the mapping
        is spread as keyword arguments. An injected ``state`` is appended as a
        reserved ``state`` keyword.
        """
        if self._args_validator is not None:
            positional: tuple[Any, ...] = (self._args_validator(arguments),)
            keyword: dict[str, Any] = {}
        else:
            positional = ()
            keyword = dict(arguments)
        if self._is_stateful:
            keyword["state"] = self._state
        return positional, keyword

    def stream(self, arguments: Mapping[str, Any]) -> AsyncIterator[Any]:
        """Return the async iterator of partial results for ``arguments``.

        Raises
        ------
        TypeError
            If this tool is not a streaming (async-generator) tool.
        """
        if not self._is_streaming:
            raise TypeError(f"tool {self._name!r} is not a streaming tool")
        positional, keyword = self._prepare_call(arguments)
        return self._fn(*positional, **keyword)

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        """Call the wrapped function with ``arguments``.

        Async functions are awaited directly; sync functions run in a thread
        via ``asyncio.to_thread`` so the event loop is never blocked. Streaming
        tools are drained and their chunks returned as a list, so callers that
        expect a single value keep working.
        """
        if self._is_streaming:
            return [chunk async for chunk in self.stream(arguments)]
        positional, keyword = self._prepare_call(arguments)
        if self._is_async:
            return await self._fn(*positional, **keyword)
        return await asyncio.to_thread(self._fn, *positional, **keyword)

    def describe(self) -> dict[str, Any]:
        """Return the full tool descriptor: name, description, params, returns, perms.

        ``returns`` is present only when the return type is annotated;
        ``permissions`` only when non-default. The neutral
        ``{name, description, parameters}`` core matches
        :meth:`pirn_agents.toolset.Toolset.schema` entries.
        """
        descriptor: dict[str, Any] = {
            "name": self._name,
            "description": self._description,
            "parameters": dict(self._parameters_schema),
        }
        if self._return_schema is not None:
            descriptor["returns"] = dict(self._return_schema)
        fragment = self._permissions.as_schema_fragment()
        if fragment:
            descriptor["permissions"] = fragment
        return descriptor

    def __repr__(self) -> str:
        return f"<FunctionTool name={self._name!r}>"
