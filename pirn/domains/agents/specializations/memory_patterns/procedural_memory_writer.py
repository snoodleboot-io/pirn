"""``ProceduralMemoryWriter`` — persist a (task, response) recipe.

Inner stage knot used by :class:`ProceduralMemoryPipeline`. The
incoming :class:`AgentResponse` content is paired with a task
description string and stored under a key prefixed with
``"procedure:"`` so callers can later replay the recipe.

Algorithm
---------
1. Validate inputs.
2. Compute ``sha1(task_description)`` for a deterministic key.
3. Persist the payload and return the key.

Math
----
``key = "procedure:" + sha1(task_description.encode()).hexdigest()``

References
----------
None.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.types.agent_response import AgentResponse


class ProceduralMemoryWriter(Knot):
    """Stores a procedural memory entry in a :class:`MemoryStore`."""

    def __init__(
        self,
        *,
        agent_response: Knot | AgentResponse,
        task_description: Knot | str,
        store: Knot | MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            agent_response=agent_response,
            task_description=task_description,
            store=store,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        agent_response: AgentResponse,
        task_description: str,
        store: MemoryStore,
        **_: Any,
    ) -> str:
        """Store a task-to-response recipe under a hash-keyed procedure entry and return the key.

        Args:
            agent_response: The agent response paired with the task as a how-to recipe.
            task_description: The non-empty task description used to derive the storage key.
            store: The MemoryStore to write the procedure into.

        Returns:
            The storage key under which the procedure was persisted.

        Raises:
            TypeError: If agent_response is not an AgentResponse or store is not a MemoryStore.
            ValueError: If task_description is not a non-empty string.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"ProceduralMemoryWriter: store must be a MemoryStore, got {type(store).__name__}"
            )
        if not isinstance(agent_response, AgentResponse):
            raise TypeError(
                "ProceduralMemoryWriter: agent_response must be an "
                f"AgentResponse, got {type(agent_response).__name__}"
            )
        if not isinstance(task_description, str) or not task_description:
            raise ValueError("ProceduralMemoryWriter: task_description must be a non-empty string")
        digest = hashlib.sha1(task_description.encode("utf-8")).hexdigest()
        key = f"procedure:{digest}"
        payload: dict[str, Any] = {
            "task": task_description,
            "response": agent_response.content,
            "finish_reason": agent_response.finish_reason,
            "stored_at": datetime.now(UTC).isoformat(),
        }
        await store.store(key, payload)
        return key
