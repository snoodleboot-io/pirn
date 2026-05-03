"""``EpisodicEpisodeWriter`` — persist a tuple of messages as one episode.

Inner stage knot used by :class:`EpisodicMemoryPipeline`. Serialises
the supplied ``tuple[AgentMessage, ...]`` into a payload mapping and
calls :meth:`MemoryStore.store` under a key of the form
``"episode:<session_id>:<created_at_iso>"``. The created-at value of
the most recent message is used for the timestamp slot so the key is
deterministic for a given conversation tail.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.types.agent_message import AgentMessage


class EpisodicEpisodeWriter(Knot):
    """Writes one conversational episode to a :class:`MemoryStore`."""

    def __init__(
        self,
        *,
        messages: Knot | Sequence[AgentMessage],
        session_id: str,
        store: MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "EpisodicEpisodeWriter: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(session_id, str) or not session_id:
            raise ValueError(
                "EpisodicEpisodeWriter: session_id must be a non-empty string, "
                f"got {session_id!r}"
            )
        self._store = store
        self._session_id = session_id
        super().__init__(messages=messages, _config=_config, **kwargs)

    async def process(
        self,
        messages: Sequence[AgentMessage],
        **_: Any,
    ) -> str:
        """Serialize the message tuple as an episode and persist it, returning the storage key.

        Args:
            messages: The sequence of agent messages forming this episode.

        Returns:
            The storage key under which the episode was persisted.

        Raises:
            TypeError: If any element of messages is not an AgentMessage.
        """
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
            timestamp = datetime.now(timezone.utc)
        key = f"episode:{self._session_id}:{timestamp.isoformat()}"
        payload: dict[str, Any] = {
            "session_id": self._session_id,
            "created_at": timestamp.isoformat(),
            "messages": [m._pirn_audit_dict() for m in message_tuple],
        }
        await self._store.store(key, payload)
        return key
