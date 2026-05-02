"""``ParallelSpecialistFanOut`` — invoke multiple specialists concurrently.

A :class:`SubTapestry` that fans out a single task string to every
registered specialist in parallel via :func:`asyncio.gather`. Each
specialist must expose a ``process(task: str, **_: Any) -> AgentResponse``
shape. The pipeline returns a mapping ``{specialist_name: AgentResponse}``.
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
        specialists: Mapping[str, SubTapestry],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(specialists, Mapping) or not specialists:
            raise ValueError(
                "ParallelSpecialistFanOut: specialists must be a non-empty "
                "mapping"
            )
        for name, candidate in specialists.items():
            if not isinstance(name, str) or not name:
                raise ValueError(
                    "ParallelSpecialistFanOut: specialist names must be "
                    f"non-empty strings, got {name!r}"
                )
            if not isinstance(candidate, SubTapestry):
                raise TypeError(
                    f"ParallelSpecialistFanOut: specialists[{name!r}] must be "
                    f"a SubTapestry, got {type(candidate).__name__}"
                )
        self._specialists: dict[str, SubTapestry] = dict(specialists)
        super().__init__(task=task, _config=_config, **kwargs)

    async def process(
        self,
        task: str,
        **_: Any,
    ) -> Mapping[str, AgentResponse]:
        if not isinstance(task, str):
            raise TypeError(
                "ParallelSpecialistFanOut: task must be a string, "
                f"got {type(task).__name__}"
            )
        names = list(self._specialists.keys())
        coros = [
            self._specialists[name].process(task=task) for name in names
        ]
        raw_results = await asyncio.gather(*coros)
        materialised: dict[str, AgentResponse] = {}
        for name, raw in zip(names, raw_results, strict=True):
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
