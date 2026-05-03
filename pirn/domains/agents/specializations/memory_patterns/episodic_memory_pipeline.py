"""``EpisodicMemoryPipeline`` — store a conversation episode.

A :class:`SubTapestry` that wraps :class:`EpisodicEpisodeWriter` so
agent flows can persist per-session conversational episodes via a
single composed knot. The pipeline returns the storage key the
episode was written under.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.memory_patterns.episodic_episode_writer import (
    EpisodicEpisodeWriter,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class EpisodicMemoryPipeline(SubTapestry):
    """Persists per-conversation episodes keyed by ``session_id``."""

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
                "EpisodicMemoryPipeline: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(session_id, str) or not session_id:
            raise ValueError(
                "EpisodicMemoryPipeline: session_id must be a non-empty "
                f"string, got {session_id!r}"
            )
        self._store = store
        self._session_id = session_id
        super().__init__(messages=messages, _config=_config, **kwargs)

    async def process(
        self,
        messages: Sequence[AgentMessage],
        **_: Any,
    ) -> str:
        """Store the conversation messages as a new episode and return the episode storage key.

        Args:
            messages: The sequence of agent messages forming the episode to persist.

        Returns:
            The storage key under which the episode was persisted.

        Raises:
            RuntimeError: If the inner writer does not return a key.
        """
        seed_messages = tuple(messages)
        with Tapestry() as inner:
            EpisodicEpisodeWriter(
                messages=seed_messages,
                session_id=self._session_id,
                store=self._store,
                _config=KnotConfig(id="write_episode"),
            )
        inner_result = await self._run_inner(inner)
        key = inner_result.outputs.get("write_episode")
        if not isinstance(key, str):
            raise RuntimeError(
                "EpisodicMemoryPipeline: inner write did not return a key"
            )
        return key
