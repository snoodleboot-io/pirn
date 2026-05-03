"""``WorkingMemoryPipeline`` — sliding-window short-term memory.

A :class:`SubTapestry` that wraps :class:`WorkingMemoryWindowWriter`.
Each invocation appends ``new_message`` to the per-session window,
evicts older entries when ``max_size`` is exceeded, and returns the
trimmed window as a tuple of :class:`AgentMessage`.
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
        session_id: str,
        store: MemoryStore,
        _config: KnotConfig,
        max_size: int = 20,
        **kwargs: Any,
    ) -> None:
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
        self._session_id = session_id
        self._store = store
        self._max_size = max_size
        super().__init__(new_message=new_message, _config=_config, **kwargs)

    async def process(
        self,
        new_message: AgentMessage,
        **_: Any,
    ) -> tuple[AgentMessage, ...]:
        """Append new_message to the session window and return the trimmed context tuple.

        Args:
            new_message: The new message to append to the per-session window.

        Returns:
            A tuple of the most recent AgentMessage instances trimmed to max_size.

        Raises:
            RuntimeError: If the inner window writer does not return a tuple.
        """
        with Tapestry() as inner:
            WorkingMemoryWindowWriter(
                new_message=new_message,
                session_id=self._session_id,
                store=self._store,
                max_size=self._max_size,
                _config=KnotConfig(id="window"),
            )
        inner_result = await self._run_inner(inner)
        window = inner_result.outputs.get("window")
        if not isinstance(window, tuple):
            raise RuntimeError(
                "WorkingMemoryPipeline: inner writer did not return a tuple"
            )
        return window
