"""``ProceduralMemoryPipeline`` — record a successful agent recipe.

A :class:`SubTapestry` wrapping :class:`ProceduralMemoryWriter`. Used
to capture how-to recipes derived from successful agent runs so
future agents can short-circuit similar tasks.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.memory_patterns.procedural_memory_writer import (
    ProceduralMemoryWriter,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class ProceduralMemoryPipeline(SubTapestry):
    """Persists ``(task_description, agent_response.content)`` recipes."""

    def __init__(
        self,
        *,
        agent_response: Knot | AgentResponse,
        task_description: Knot | str,
        store: MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "ProceduralMemoryPipeline: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
        self._store = store
        super().__init__(
            agent_response=agent_response,
            task_description=task_description,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        agent_response: AgentResponse,
        task_description: str,
        **_: Any,
    ) -> str:
        """Persist the task-response recipe in the store and return the procedure key.

        Args:
            agent_response: The agent response whose content forms the recipe.
            task_description: The natural-language task description paired with the response.

        Returns:
            The storage key under which the procedure was persisted.

        Raises:
            RuntimeError: If the inner writer does not return a key.
        """
        with Tapestry() as inner:
            ProceduralMemoryWriter(
                agent_response=agent_response,
                task_description=task_description,
                store=self._store,
                _config=KnotConfig(id="write_procedure"),
            )
        inner_result = await self._run_inner(inner)
        key = inner_result.outputs.get("write_procedure")
        if not isinstance(key, str):
            raise RuntimeError(
                "ProceduralMemoryPipeline: inner write did not return a key"
            )
        return key
