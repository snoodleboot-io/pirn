"""``OrchestratorAgent`` — top-level coordinator with specialist routing.

A :class:`SubTapestry` that:

1. Asks an LLM (via :class:`OrchestratorRouter`) to pick the best
   specialist for the supplied task.
2. Invokes that specialist's ``process`` with ``task=task`` and
   returns the resulting :class:`AgentResponse`.

Specialists are expected to accept a ``task: str`` kwarg and return
an :class:`AgentResponse`. They run as sub-pipelines outside the
orchestrator's inner :class:`Tapestry`; only the routing decision is
recorded as an inner knot.

Algorithm:
    1. Validate ``llm``, ``specialists`` (non-empty mapping), and ``task`` (str).
    2. Build an inner :class:`Tapestry` containing :class:`OrchestratorRouter`
       with the specialist names.
    3. Execute via ``self._run_inner(inner)`` to obtain the routing decision.
    4. Look up the chosen specialist by name; fall back to the first on mismatch.
    5. Call ``specialist.process(task=task)`` and normalise to :class:`AgentResponse`.


References:
    pirn-native — no external references.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.domains.agents.specializations.multi_agent.orchestrator_router import (
    OrchestratorRouter,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class OrchestratorAgent(SubTapestry):
    """Routes a task to one of a registered specialist :class:`SubTapestry`."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: Knot | LLMProvider,
        specialists: Knot | Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(task=task, llm=llm, specialists=specialists, _config=_config, **kwargs)

    async def process(
        self,
        task: str,
        llm: LLMProvider,
        specialists: Any,
        **_: Any,
    ) -> Any:
        """Route the task to the LLM-selected specialist and return its AgentResponse.

        Args:
            task: The natural-language task string to route to a specialist.

        Returns:
            The AgentResponse produced by the selected specialist.

        Raises:
            TypeError: If task is not a string.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"OrchestratorAgent: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(specialists, Mapping) or not specialists:
            raise ValueError("OrchestratorAgent: specialists must be a non-empty mapping")
        if not isinstance(task, str):
            raise TypeError(f"OrchestratorAgent: task must be a string, got {type(task).__name__}")
        specialists_dict: dict[str, SubTapestry] = dict(specialists)  # type: ignore[arg-type]
        with Tapestry() as route_inner:
            OrchestratorRouter(
                task=task,
                llm=llm,
                specialist_names=tuple(specialists_dict.keys()),
                _config=KnotConfig(id="route"),
            )
        route_result = await self._run_inner(route_inner)
        chosen_name = route_result.outputs.get("route")
        if not isinstance(chosen_name, str):
            chosen_name = next(iter(specialists_dict))
        specialist = specialists_dict[chosen_name]
        raw = await specialist.process(task=task)
        final: AgentResponse = (
            raw
            if isinstance(raw, AgentResponse)
            else AgentResponse(content=str(raw), finish_reason="stop")
        )

        _final = final

        class _ResultSource(Source):
            async def process(self, **_: Any) -> AgentResponse:
                return _final

        return _ResultSource(_config=KnotConfig(id="result"))
