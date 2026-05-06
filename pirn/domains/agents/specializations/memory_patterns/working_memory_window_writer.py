"""``WorkingMemoryWindowWriter`` — sliding-window write to a MemoryStore.

Inner stage knot used by :class:`WorkingMemoryPipeline`. Reads the
existing window stored under ``"working:<session_id>"`` (if any),
appends ``new_message``, trims to ``max_size`` items, and writes the
result back. Returns the trimmed tuple of messages.

Algorithm
---------
1. Validate inputs.
2. Retrieve existing window from ``store`` under key ``working:<session_id>``.
3. Append ``new_message``; trim to the last ``max_size`` elements.
4. Persist the updated window and return it as a tuple.

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
from pirn.domains.agents.types.agent_message import AgentMessage


class WorkingMemoryWindowWriter(Knot):
    """Maintains a per-session sliding window in a :class:`MemoryStore`."""

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
        """Append new_message to the stored session window, trim to max_size, persist, and return the window.

        Args:
            new_message: The message to append to the session window.
            session_id: Non-empty string identifying the session.
            store: The MemoryStore for reading and writing the window.
            max_size: Maximum number of messages to retain in the window.

        Returns:
            A tuple of the most recent AgentMessage entries after trimming to max_size.

        Raises:
            TypeError: If store is not a MemoryStore or new_message is not an AgentMessage.
            ValueError: If session_id is not a non-empty string or max_size is not a positive int.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "WorkingMemoryWindowWriter: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(session_id, str) or not session_id:
            raise ValueError(
                "WorkingMemoryWindowWriter: session_id must be a non-empty "
                f"string, got {session_id!r}"
            )
        if not isinstance(max_size, int) or max_size <= 0:
            raise ValueError(
                "WorkingMemoryWindowWriter: max_size must be a positive int, "
                f"got {max_size!r}"
            )
        if not isinstance(new_message, AgentMessage):
            raise TypeError(
                "WorkingMemoryWindowWriter: new_message must be an "
                f"AgentMessage, got {type(new_message).__name__}"
            )
        key = f"working:{session_id}"
        existing = await store.retrieve(key)
        prior: tuple[AgentMessage, ...] = ()
        if existing is not None:
            stored = existing.get("messages")
            if isinstance(stored, (list, tuple)):
                collected: list[AgentMessage] = []
                for entry in stored:
                    if isinstance(entry, AgentMessage):
                        collected.append(entry)
                prior = tuple(collected)
        combined: tuple[AgentMessage, ...] = (*prior, new_message)
        if len(combined) > max_size:
            combined = combined[-max_size:]
        await store.store(
            key,
            {"session_id": session_id, "messages": list(combined)},
        )
        return combined
