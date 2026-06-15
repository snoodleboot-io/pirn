"""``EpisodicEpisodeWriter`` — persist a tuple of messages as one episode.

Inner stage knot used by :class:`EpisodicMemoryPipeline`. Serialises
the supplied ``tuple[AgentMessage, ...]`` into a payload mapping and
calls :meth:`MemoryStore.store` under a key of the form
``"episode:<session_id>:<created_at_iso>"``. The created-at value of
the most recent message is used for the timestamp slot so the key is
deterministic for a given conversation tail.

Algorithm
---------
1. Validate every element of ``messages`` is an :class:`AgentMessage`.
2. Derive the timestamp from the last message's ``created_at`` field,
   falling back to ``datetime.now(UTC)`` for empty sequences.
3. Compose the key ``episode:<session_id>:<timestamp_iso>``.
4. Call ``store.store(key, payload)`` and return the key.

Math
----
No mathematical operations.

References
----------
None.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory_store import MemoryStore
from pirn_agents.types.agent_message import AgentMessage


class EpisodicEpisodeWriter(Knot):
    """Writes one conversational episode to a :class:`MemoryStore`."""

    def __init__(
        self,
        *,
        messages: Knot | Sequence[AgentMessage],
        session_id: Knot | str,
        store: Knot | MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            messages=messages, session_id=session_id, store=store, _config=_config, **kwargs
        )

    async def process(
        self,
        messages: Sequence[AgentMessage],
        session_id: str,
        store: MemoryStore,
        **_: Any,
    ) -> str:
        """Serialize the message tuple as an episode and persist it, returning the storage key.

        Args:
            messages: The sequence of agent messages forming this episode.
            session_id: Non-empty string identifying the session.
            store: The MemoryStore to write the episode into.

        Returns:
            The storage key under which the episode was persisted.

        Raises:
            TypeError: If store is not a MemoryStore or any message element is not an AgentMessage.
            ValueError: If session_id is not a non-empty string.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"EpisodicEpisodeWriter: store must be a MemoryStore, got {type(store).__name__}"
            )
        if not isinstance(session_id, str) or not session_id:
            raise ValueError(
                f"EpisodicEpisodeWriter: session_id must be a non-empty string, got {session_id!r}"
            )
        message_tuple = tuple(messages)
        for index, candidate in enumerate(message_tuple):
            if not isinstance(candidate, AgentMessage):
                raise TypeError(
                    f"EpisodicEpisodeWriter: messages[{index}] must be an "
                    f"AgentMessage, got {type(candidate).__name__}"
                )
        if message_tuple:
            timestamp = message_tuple[-1].created_at
        else:
            timestamp = datetime.now(UTC)
        key = f"episode:{session_id}:{timestamp.isoformat()}"
        payload: dict[str, Any] = {
            "session_id": session_id,
            "created_at": timestamp.isoformat(),
            "messages": [m._pirn_audit_dict() for m in message_tuple],
        }
        await store.store(key, payload)
        return key
