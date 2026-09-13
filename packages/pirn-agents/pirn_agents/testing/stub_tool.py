"""``StubTool`` — a configurable, deterministic tool double for tests.

:class:`StubTool` generalises the ad-hoc stubs the agent tests grow locally: a
single tool capability that can act as a plain sync/async tool, a streaming
tool, or a stateful tool, records every call, and lets a test pin its schema,
return schema, and permissions. It ships in the package (not just the test
tree) so external tool authors can reuse it through the testing kit.

Since the ADR "agents speaks core" (WS1) a tool is a ``Knot`` class and a
capability is a :class:`~pirn_agents.tools.tool_factory.ToolFactory`.
``StubTool`` is such a factory: each configuration generates its own
schema-declared :class:`~pirn_agents.tools.tool.Tool` subclass whose
``process()`` records the call and returns the configured value, so a stub
runs through the engine exactly like a real tool (``stub.for_call(call)`` in
a tapestry, or ``await stub.run_call(call)`` for a bare ``Result``).  The
declared schema is open by default — ``{"input": {"type": "string"}}`` with
any extra argument accepted — so a stub can stand in for any call shape.
"""

from __future__ import annotations

import functools
import weakref
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from inspect import isawaitable
from typing import Any

from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_permissions import ToolPermissions


class StubTool(ToolFactory):
    """A deterministic tool capability double for exercising the testing kit.

    Configure exactly one behaviour:

    * default / ``result`` — a call returns ``result``.
    * ``handler`` — a call returns ``handler(arguments)`` (awaited if it
      returns an awaitable).
    * ``stream_chunks`` — the tool becomes streaming; :meth:`stream` yields the
      chunks and a call returns them as a list.

    Passing ``state`` makes the tool stateful; the object is exposed via
    :attr:`state` and persists across calls unchanged.  ``invocations``
    records every call's arguments, in order.
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
        declared: dict[str, Any] = (
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
        # The knot declares one packed ``arguments`` input so any call shape
        # is accepted; the declaration shown to a model is ``declared``.
        knot_class = ToolFactory.schema_declared_class(
            f"StubTool_{name}",
            {
                "type": "object",
                "properties": {"arguments": {"type": "object"}},
                "required": ["arguments"],
            },
            # A weak reference, not ``self._run``: the generated class must
            # not keep its factory alive, so a dropped stub is freed by
            # reference count like any other value (PIR-852's reuse loops).
            functools.partial(StubTool._run_via, weakref.ref(self)),
            description=description,
            tool_name=name,
        )
        super().__init__(knot_class, name=name, description=description, parameters=declared)
        self._packs_arguments = True

    @staticmethod
    async def _run_via(ref: weakref.ref[StubTool], **kwargs: Any) -> Any:
        """Resolve the stub behind ``ref`` and run it; a collected stub cannot be called."""
        stub = ref()
        if stub is None:
            raise RuntimeError("StubTool: the stub behind this call has been garbage-collected")
        return await stub._run(**kwargs)

    async def _run(self, **kwargs: Any) -> Any:
        """The generated knot's body: record the call and produce the configured value."""
        arguments: Mapping[str, Any] = kwargs.get("arguments", {})
        self.invocations.append(dict(arguments))
        if self._stream_chunks is not None:
            return [chunk async for chunk in self.stream(arguments)]
        if self._handler is not None:
            outcome = self._handler(arguments)
            if isawaitable(outcome):
                return await outcome
            return outcome
        return self._result

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
            raise TypeError(f"stub tool {self.name!r} is not a streaming tool")
        self.stream_invocations.append(dict(arguments))
        return self._iterate(list(self._stream_chunks))

    @staticmethod
    async def _iterate(chunks: list[Any]) -> AsyncIterator[Any]:
        """Yield ``chunks`` one at a time (a snapshot, independent of later reconfiguration)."""
        for chunk in chunks:
            yield chunk

    def describe(self) -> dict[str, Any]:
        """The declaration payload plus ``returns`` and non-default ``permissions``."""
        descriptor = super().describe()
        if self._return_schema is not None:
            descriptor["returns"] = dict(self._return_schema)
        return descriptor

    def __repr__(self) -> str:
        return f"<StubTool name={self.name!r}>"
