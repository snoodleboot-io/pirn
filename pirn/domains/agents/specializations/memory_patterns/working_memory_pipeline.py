"""``WorkingMemoryPipeline`` — sliding-window short-term memory.

A :class:`SubTapestry` that wraps :class:`WorkingMemoryWindowWriter`.
Each invocation appends ``new_message`` to the per-session window,
evicts older entries when ``max_size`` is exceeded, and returns the
trimmed window as a tuple of :class:`AgentMessage`.

Algorithm
---------
1. Validate inputs.
2. Construct an inner Tapestry with :class:`WorkingMemoryWindowWriter`.
3. Run the inner tapestry via ``self._run_inner(inner)``.
4. Extract and return the window tuple.

Math
----
No mathematical operations.

References
----------
None.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.memory_patterns.working_memory_window_writer import (
    WorkingMemoryWindowWriter,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class WorkingMemoryPipeline(SubTapestry):
    """Maintains a short-window buffer of recent context per session."""

    def __init__(
        self,
        *,
        new_message: Knot | AgentMessage,
        session_id: Knot | str,
        store: Knot | MemoryStore,
        max_size: Knot | int = 20,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            new_message=new_message,
            session_id=session_id,
            store=store,
            max_size=max_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        new_message: AgentMessage,
        session_id: str,
        store: MemoryStore,
        max_size: int = 20,
        **_: Any,
    ) -> tuple[AgentMessage, ...]:
        """Append new_message to the session window and return the trimmed context tuple.

        Args:
            new_message: The new message to append to the per-session window.
            session_id: Non-empty string identifying the session.
            store: The MemoryStore for reading and writing the window.
            max_size: Maximum number of messages to retain in the window.

        Returns:
            A tuple of the most recent AgentMessage instances trimmed to max_size.

        Raises:
            TypeError: If store is not a MemoryStore.
            ValueError: If session_id is not a non-empty string or max_size is not a positive int.
            RuntimeError: If the inner window writer does not return a tuple.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "WorkingMemoryPipeline: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(session_id, str) or not session_id:
            raise ValueError(
                "WorkingMemoryPipeline: session_id must be a non-empty "
                f"string, got {session_id!r}"
            )
        if not isinstance(max_size, int) or max_size <= 0:
            raise ValueError(
                "WorkingMemoryPipeline: max_size must be a positive int, "
                f"got {max_size!r}"
            )
        with Tapestry() as inner:
            WorkingMemoryWindowWriter(
                new_message=new_message,
                session_id=session_id,
                store=store,
                max_size=max_size,
                _config=KnotConfig(id="window"),
            )
        inner_result = await self._run_inner(inner)
        window = inner_result.outputs.get("window")
        if not isinstance(window, tuple):
            raise RuntimeError(
                "WorkingMemoryPipeline: inner writer did not return a tuple"
            )
        return window
