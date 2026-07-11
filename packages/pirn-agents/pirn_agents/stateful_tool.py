"""``StatefulTool`` — structural contract for tools holding injected state.

A stateful tool is handed a state or resource object once (at construction or
registration) and keeps it across invocations: a database handle, an in-memory
scratchpad, a :class:`~pirn_agents.memory_store.MemoryStore`. Because the same
object is threaded through every call, mutations made during one invocation are
visible to the next.

:class:`StatefulTool` is a :func:`~typing.runtime_checkable`
:class:`~typing.Protocol` capturing that shape — a truthy ``stateful`` flag and
a ``state`` attribute holding the injected object. The :func:`supports_state`
predicate is the single check callers use.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StatefulTool(Protocol):
    """A tool that holds injected state/resources across invocations."""

    @property
    def stateful(self) -> bool:
        """Return ``True`` when this tool carries injected state."""
        ...

    @property
    def state(self) -> Any:
        """Return the injected state/resource object, or ``None``."""
        ...


def supports_state(tool: object) -> bool:
    """Return whether ``tool`` carries injected state across calls.

    A tool qualifies when it satisfies the :class:`StatefulTool` shape *and*
    its ``stateful`` flag is truthy.
    """
    return isinstance(tool, StatefulTool) and bool(tool.stateful)
