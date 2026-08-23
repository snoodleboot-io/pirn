"""``ParallelSpecialistFanOut`` — invoke multiple specialists concurrently.

A :class:`SubTapestry` that fans out a single task string to every registered
specialist and returns a mapping ``{specialist_name: AgentResponse}``.

The fan-out is expressed as a graph, not as an ad-hoc ``asyncio.gather``: each
specialist becomes one :class:`SpecialistInvocation` knot, and all of them are
wired as the parents of a single :class:`~pirn.nodes.aggregator.Aggregator`.
The engine then schedules the whole wave concurrently — every ready sibling
runs in one ``asyncio.gather`` inside the scheduler — so the specialists run
*through* the engine rather than outside it. See PIR-714.

Failure mode is UNCHANGED by this rewrite. If any invocation fails, the inner
``tapestry.run`` records an exception and :class:`SubTapestryError` is raised
for the whole knot (``sub_tapestry.py``), exactly as the old ``asyncio.gather``
surfaced the first failure. No per-specialist error isolation is gained — that
would need a core change and is out of scope.

Per-specialist lineage is NOT in the outer ``run.outputs`` (the inner knots run
in a separate inner ``RunResult``). To reach it, read
``lineage[].extra['inner_run_id']`` and look that run up in history — and note
that on the failure path ``inner_run_id`` may be absent, so a sibling's ``Ok``
record has no retrieval path there.

Algorithm:
    1. Validate ``specialists`` (non-empty mapping) and ``task`` (str).
    2. Build one :class:`SpecialistInvocation` per specialist, each holding its
       specialist on a ``_mutable_`` slot and receiving the shared ``task``.
    3. Wire all invocations as parents of an :class:`Aggregator` whose combine
       reassembles the ``{name: AgentResponse}`` mapping in registration order.
    4. Return the aggregator as the inner pipeline's sink.


References:
    pirn-native — no external references.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.multi_agent.specialist_invocation import (
    SpecialistInvocation,
)
from pirn_agents.types.messaging.agent_response import AgentResponse


def _make_mapping_combine(
    order: list[tuple[str, str]],
) -> Any:
    """Build the aggregator combine that reassembles ``{name: response}``.

    ``order`` pairs each parent kwarg key with its original specialist name, so
    the mapping is rebuilt in the specialists' registration order regardless of
    the keys used to wire the parents.
    """

    def combine(**responses: AgentResponse) -> dict[str, AgentResponse]:
        return {name: responses[key] for key, name in order}

    return combine


class ParallelSpecialistFanOut(AgentPipeline):
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
    ) -> Knot:
        """Fan the task out to all specialists and return the aggregating sink knot.

        Args:
            task: The task string sent to every registered specialist.

        Returns:
            The :class:`Aggregator` sink whose output is the name-to-response mapping.

        Raises:
            ValueError: If specialists is empty or not a Mapping.
            TypeError: If task is not a string.
        """
        if not isinstance(specialists, Mapping) or not specialists:
            raise ValueError("ParallelSpecialistFanOut: specialists must be a non-empty mapping")
        if not isinstance(task, str):
            raise TypeError(
                f"ParallelSpecialistFanOut: task must be a string, got {type(task).__name__}"
            )
        specialists_dict: dict[str, SubTapestry] = dict(specialists)  # type: ignore[arg-type]
        parents: dict[str, Knot] = {}
        order: list[tuple[str, str]] = []
        for index, (name, specialist) in enumerate(specialists_dict.items()):
            key = f"invocation_{index}"
            parents[key] = SpecialistInvocation(
                specialist=specialist,
                task=task,
                _config=KnotConfig(id=f"invoke_{index}"),
            )
            order.append((key, name))
        return Aggregator(
            combine=_make_mapping_combine(order),
            _config=KnotConfig(id="fan_out_aggregate"),
            **parents,
        )
