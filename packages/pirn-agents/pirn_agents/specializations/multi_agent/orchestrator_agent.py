"""``OrchestratorAgent`` — top-level coordinator with specialist routing.

A :class:`SubTapestry` that:

1. Asks an LLM (via :class:`OrchestratorRouter`) to pick the best
   specialist for the supplied task.
2. Invokes that specialist through its engine entry point with
   ``task=task`` and returns the resulting :class:`AgentResponse`.

Specialists are expected to accept a ``task: str`` kwarg. As
:class:`SubTapestry` instances their ``process()`` returns the *sink knot*
of their inner pipeline, so they must be invoked via
:meth:`SpecialistHandle.run` — calling ``process()`` directly hands back an
unexecuted :class:`Knot` (see PIR-769). They run as sub-pipelines outside
the orchestrator's inner :class:`Tapestry`; only the routing decision is
recorded as an inner knot.

Algorithm:
    1. Validate ``llm``, ``specialists`` (non-empty mapping), and ``task`` (str).
    2. Build an inner :class:`Tapestry` containing :class:`OrchestratorRouter`
       with the specialist names.
    3. Execute via ``self._run_inner(inner)`` to obtain the routing decision.
    4. Look up the chosen specialist by name; fall back to the first on mismatch.
    5. Run the specialist via :meth:`SpecialistHandle.run` and normalise the value
       it produced to an :class:`AgentResponse`.


References:
    pirn-native — no external references.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.multi_agent.orchestrator_result_normalizer import (
    OrchestratorResultNormalizer,
)
from pirn_agents.specializations.multi_agent.orchestrator_router import (
    OrchestratorRouter,
)
from pirn_agents.specializations.multi_agent.specialist_handle import SpecialistHandle


class OrchestratorAgent(AgentPipeline):
    """Routes a task to one of a registered specialist :class:`SubTapestry`."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: Knot | LLMProvider,
        specialists: Knot | Mapping[str, SubTapestry],
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
    ) -> Knot:
        """Route the task to the LLM-selected specialist and return its AgentResponse.

        Args:
            task: The natural-language task string to route to a specialist.

        Returns:
            The AgentResponse produced by the selected specialist.
        """
        specialists_dict = SpecialistHandle.by_name(specialists, owner="OrchestratorAgent")
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
        raw = await SpecialistHandle(specialist).run(task=task)
        return OrchestratorResultNormalizer(raw=raw, _config=KnotConfig(id="result"))
