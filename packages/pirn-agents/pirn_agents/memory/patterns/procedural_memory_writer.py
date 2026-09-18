"""``ProceduralMemoryWriter`` — persist a (task, response) recipe.

Inner stage knot used by :class:`ProceduralMemoryPipeline`. The
incoming :class:`AgentResponse` content is paired with a task
description string and stored under a key prefixed with
``"procedure:"`` so callers can later replay the recipe.

Algorithm
---------
1. Validate inputs.
2. Content-address ``task_description`` through
   :class:`~pirn.core.content_hasher.ContentHasher` for a deterministic key.
3. Read the storage timestamp from the injected
   :class:`~pirn_agents.determinism.clock.Clock`.
4. Persist the payload and return the key.

Math
----
``key = "procedure:" + ContentHasher.hash(task_description)``

The digest was a bare ``hashlib.sha1`` of the UTF-8 bytes; ``ContentHasher`` is
the workspace's one content-addressing seam (canonical serialisation, sha256,
the same hash lineage joins on), so a key derived here and a hash computed
anywhere else agree (PIR-873).

References
----------
None.
"""

from __future__ import annotations

from typing import Any

from pirn.core.content_hasher import ContentHasher
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.determinism.clock import Clock
from pirn_agents.determinism.system_clock import SystemClock
from pirn_agents.memory.memory_writer_base import MemoryWriterBase
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.types.messaging.agent_response import AgentResponse


class ProceduralMemoryWriter(MemoryWriterBase):
    """Stores a procedural memory entry in a :class:`MemoryStore`."""

    def __init__(
        self,
        *,
        agent_response: Knot | AgentResponse,
        task_description: Knot | str,
        store: Knot | MemoryStore,
        _config: KnotConfig,
        clock: Knot | Clock | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            agent_response=agent_response,
            task_description=task_description,
            store=store,
            clock=clock,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        agent_response: AgentResponse,
        task_description: str,
        store: MemoryStore,
        clock: Clock | None = None,
        **_: Any,
    ) -> str:
        """Store a task-to-response recipe under a hash-keyed procedure entry and return the key.

        Args:
            agent_response: The agent response paired with the task as a how-to recipe.
            task_description: The non-empty task description used to derive the storage key.
            store: The MemoryStore to write the procedure into.
            clock: The run's time source; a ``FrozenClock`` under a
                deterministic run makes ``stored_at`` reproducible.  Defaults
                to a :class:`SystemClock` — the wall clock is never read
                directly (PIR-873).

        Returns:
            The storage key under which the procedure was persisted.

        Raises:
            ValueError: If task_description is not a non-empty string.
        """
        if not isinstance(task_description, str) or not task_description:
            raise ValueError("ProceduralMemoryWriter: task_description must be a non-empty string")
        key = f"procedure:{ContentHasher.hash(task_description)}"
        payload: dict[str, Any] = {
            "task": task_description,
            "response": agent_response.data,
            "finish_reason": agent_response.metadata.finish_reason,
            "stored_at": (clock if clock is not None else SystemClock()).now().isoformat(),
        }
        await store.store(key, payload)
        return key
