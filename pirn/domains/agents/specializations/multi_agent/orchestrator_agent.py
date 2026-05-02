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
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.multi_agent.orchestrator_router import (
    OrchestratorRouter,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class OrchestratorAgent(SubTapestry):
    """Routes a task to one of a registered specialist :class:`SubTapestry`."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: LLMProvider,
        specialists: Mapping[str, SubTapestry],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "OrchestratorAgent: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(specialists, Mapping) or not specialists:
            raise ValueError(
                "OrchestratorAgent: specialists must be a non-empty mapping"
            )
        for name, candidate in specialists.items():
            if not isinstance(name, str) or not name:
                raise ValueError(
                    "OrchestratorAgent: specialist names must be non-empty "
                    f"strings, got {name!r}"
                )
            if not isinstance(candidate, SubTapestry):
                raise TypeError(
                    f"OrchestratorAgent: specialists[{name!r}] must be a "
                    f"SubTapestry, got {type(candidate).__name__}"
                )
        self._llm = llm
        self._specialists: dict[str, SubTapestry] = dict(specialists)
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(self, task: str, **_: Any) -> AgentResponse:
        if not isinstance(task, str):
            raise TypeError(
                "OrchestratorAgent: task must be a string, "
                f"got {type(task).__name__}"
            )
        with Tapestry() as inner:
            OrchestratorRouter(
                task=task,
                llm=self._llm,
                specialist_names=tuple(self._specialists.keys()),
                _config=KnotConfig(id="route"),
            )
        inner_result = await self._run_inner(inner)
        chosen_name = inner_result.outputs.get("route")
        if not isinstance(chosen_name, str):
            chosen_name = next(iter(self._specialists))
        specialist = self._specialists[chosen_name]
        result = await specialist.process(task=task)
        if not isinstance(result, AgentResponse):
            return AgentResponse(content=str(result), finish_reason="stop")
        return result
