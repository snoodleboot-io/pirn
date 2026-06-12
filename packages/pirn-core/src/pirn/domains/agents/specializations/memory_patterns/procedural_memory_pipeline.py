"""``ProceduralMemoryPipeline`` — record a successful agent recipe.

A :class:`SubTapestry` wrapping :class:`ProceduralMemoryWriter`. Used
to capture how-to recipes derived from successful agent runs so
future agents can short-circuit similar tasks.

Algorithm
---------
1. Validate inputs.
2. Construct an inner Tapestry with :class:`ProceduralMemoryWriter`.
3. Run the inner tapestry via ``self._run_inner(inner)``.
4. Extract and return the procedure key.

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
from pirn.domains.agents.specializations.memory_patterns.procedural_memory_writer import (
    ProceduralMemoryWriter,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry


class ProceduralMemoryPipeline(SubTapestry):
    """Persists ``(task_description, agent_response.content)`` recipes."""

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
    ) -> Any:
        """Persist the task-response recipe in the store and return the procedure key.

        Args:
            agent_response: The agent response whose content forms the recipe.
            task_description: The natural-language task description paired with the response.
            store: The MemoryStore to write the procedure into.

        Returns:
            The storage key under which the procedure was persisted.

        Raises:
            TypeError: If store is not a MemoryStore.
            RuntimeError: If the inner writer does not return a key.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"ProceduralMemoryPipeline: store must be a MemoryStore, got {type(store).__name__}"
            )
        return ProceduralMemoryWriter(
            agent_response=agent_response,
            task_description=task_description,
            store=store,
            _config=KnotConfig(id="write_procedure"),
        )
