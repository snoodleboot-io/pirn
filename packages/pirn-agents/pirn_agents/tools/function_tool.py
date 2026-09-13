"""``FunctionTool`` — the capability the ``@tool`` decorator produces.

``@tool`` is ``@knot`` plus a declaration (ADR agents-speaks-core, WS1): the
decorated function becomes the ``process()`` of a generated
:class:`~pirn_agents.tools.tool.Tool` subclass, exactly as
:class:`~pirn.core.knot_factory.KnotFactory.create` does for ``@knot`` — the
function's signature is the knot's input contract, a sync function runs via
``asyncio.to_thread``, an async-generator function is drained — and the
resulting :class:`~pirn_agents.tools.tool_factory.ToolFactory` carries the
extras only a function-backed tool has: the wrapped ``fn``, a ``return_schema``
from the return annotation, the ``stateful``/``state`` facet for an injected
resource, and :meth:`describe`.

It is constructed by :class:`~pirn_agents.tools.tool_decorator.ToolDecorator` —
not instantiated directly.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pirn.core.knot import Knot

from pirn_agents.tools.tool_factory import ToolFactory


class FunctionTool(ToolFactory):
    """A :class:`ToolFactory` over a ``Tool`` subclass generated from a plain function."""

    def __init__(
        self,
        knot_class: type[Knot],
        *,
        fn: Callable[..., Any],
        return_schema: Mapping[str, Any] | None = None,
        state: Any | None = None,
        is_stateful: bool = False,
        stream_fn: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__(knot_class, fn=fn)
        self._return_schema = dict(return_schema) if return_schema is not None else None
        self._state = state
        self._is_stateful = is_stateful
        self._stream_fn = stream_fn

    @property
    def return_schema(self) -> Mapping[str, Any] | None:
        """JSON Schema fragment for the return value, or ``None`` if untyped."""
        return self._return_schema

    @property
    def stateful(self) -> bool:
        """Whether this tool carries injected state across calls."""
        return self._is_stateful

    @property
    def state(self) -> Any | None:
        """The injected state/resource object, or ``None``."""
        return self._state

    def stream(self, arguments: Mapping[str, Any]) -> Any:
        """Return the async iterator of partial results for ``arguments``.

        Raises:
            TypeError: If this tool is not a streaming (async-generator) tool.
        """
        if self._stream_fn is None:
            raise TypeError(f"tool {self.name!r} is not a streaming tool")
        return self._stream_fn(**self.resolve_arguments(arguments))

    def describe(self) -> dict[str, Any]:
        """Return the full tool descriptor: name, description, params, returns, perms.

        ``returns`` is present only when the return type is annotated;
        ``permissions`` only when non-default. The neutral core is this tool's
        :class:`~pirn_agents.tools.tool_declaration.ToolDeclaration`, so it is
        the same triple — same keys, same order — that
        :meth:`pirn_agents.tools.toolset.Toolset.schema` emits.
        """
        descriptor: dict[str, Any] = self.declaration().to_payload()
        if self._return_schema is not None:
            descriptor["returns"] = dict(self._return_schema)
        fragment = self.permissions.as_schema_fragment()
        if fragment:
            descriptor["permissions"] = fragment
        return descriptor

    def __repr__(self) -> str:
        return f"<FunctionTool name={self.name!r}>"
