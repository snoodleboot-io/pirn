"""``ParallelSpecialistFanOut`` — invoke multiple specialists concurrently.

A :class:`SubTapestry` that fans out a single task string to every
registered specialist in parallel via :func:`asyncio.gather`. Each
specialist must expose a ``process(task: str, **_: Any) -> AgentResponse``
shape. The pipeline returns a mapping ``{specialist_name: AgentResponse}``.

Algorithm:
    1. Validate ``specialists`` (non-empty mapping) and ``task`` (str).
    2. Gather all ``specialist.process(task=task)`` coroutines concurrently.
    3. Normalise each result to an :class:`AgentResponse`.
    4. Build an inner :class:`Tapestry` with :class:`SpecialistFanOutCollector`
       over the materialised responses.
    5. Execute via ``self._run_inner(inner)`` and return the collected mapping.


References:
    pirn-native — no external references.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.multi_agent.specialist_fan_out_collector import (
    SpecialistFanOutCollector,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class ParallelSpecialistFanOut(SubTapestry):
    """Runs every registered specialist concurrently on the same task."""

    def __init__(
        self,
        *,
        task: Knot | str,
        specialists: Knot | Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(task=task, specialists=specialists, _config=_config, **kwargs)

    async def process(
        self,
        task: str,
        specialists: Any,
        **_: Any,
    ) -> Mapping[str, AgentResponse]:
        """Fan out the task to all specialists concurrently and return a name-to-response mapping.

        Args:
            task: The task string sent to every registered specialist.

        Returns:
            A mapping of specialist name to the AgentResponse produced by that specialist.

        Raises:
            TypeError: If task is not a string.
        """
        if not isinstance(specialists, Mapping) or not specialists:
            raise ValueError("ParallelSpecialistFanOut: specialists must be a non-empty mapping")
        if not isinstance(task, str):
            raise TypeError(
                f"ParallelSpecialistFanOut: task must be a string, got {type(task).__name__}"
            )
        specialists_dict: dict[str, SubTapestry] = dict(specialists)  # type: ignore[arg-type]
        names = list(specialists_dict.keys())
        coros = [specialists_dict[name].process(task=task) for name in names]
        raw_results = await asyncio.gather(*coros)
        materialised: dict[str, AgentResponse] = {}
        for name, raw in zip(names, raw_results, strict=False):
            if isinstance(raw, AgentResponse):
                materialised[name] = raw
            else:
                materialised[name] = AgentResponse(
                    content=str(raw),
                    finish_reason="stop",
                )
        with Tapestry() as inner:
            SpecialistFanOutCollector(
                responses=materialised,
                _config=KnotConfig(id="collect"),
            )
        inner_result = await self._run_inner(inner)
        collected = inner_result.outputs.get("collect")
        if not isinstance(collected, Mapping):
            return materialised
        return collected
