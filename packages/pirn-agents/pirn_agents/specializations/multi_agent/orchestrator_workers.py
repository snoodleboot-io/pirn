"""``OrchestratorWorkers`` — dynamic worker fan-out over a task list via F7.

A :class:`SubTapestry` that spawns **one worker invocation per task-list item**,
bounded by a configurable ``max_concurrency`` semaphore, and aggregates the
per-task outcomes into a typed :class:`OrchestratorWorkersResult`.

The worker is any :class:`Tool` — in practice an F7
:class:`~pirn_agents.tools.agent_tool.AgentTool` wrapping a specialist agent — so the
orchestrator reuses agents-as-tools rather than a bespoke worker abstraction. The
worker count therefore scales with the task list while wall-clock stays bounded by
the concurrency cap, exactly like the F1
:class:`~pirn_agents.agent.parallel_tool_executor.ParallelToolExecutor`.

The fan-out is expressed as a graph rather than a hand-rolled
``asyncio.gather``: each task becomes its own
:class:`~pirn_agents.specializations.multi_agent._worker_invocation._WorkerInvocation`
knot, and all of them are wired as parents of a single
:class:`~pirn.nodes.aggregator.Aggregator` — the same shape
:class:`~pirn_agents.specializations.multi_agent.parallel_specialist_fan_out.ParallelSpecialistFanOut`
uses for its (fixed, named) fan-out. The engine schedules the ready siblings
concurrently (PIR-841), so each task's call gets its own ``Result``, history
record, and lineage.

``max_concurrency`` used to be a bare ``asyncio.Semaphore`` shared across
every ``_WorkerInvocation`` and held across its real ``await worker.invoke(...)``.
PIR-867 replaced it with the engine's own admission gate: every
``_WorkerInvocation`` carries the same ``KnotConfig.concurrency_group``, and
``_inner_concurrency()`` sets a matching ``ConcurrencyLimits`` group cap on
the inner run — the lever :class:`~pirn_agents.batch.map_agent.MapAgent`
uses, inherited by inner runs via ``ExecutionPlane`` so it is the same
budget the admission gate already schedules against, not a second, private
one it cannot see. ``_WorkerInvocation`` does not nest
:class:`~pirn_agents.tools.tool_invocation.ToolInvocation` as a further inner
node — it reproduces ``ToolInvocation``'s exact catch-and-wrap contract
directly (never raises; a failed call becomes a ``ToolStatus.ERROR`` result,
scrubbed via ``ToolErrorRecord``) so results compose identically either way.

Algorithm:
    1. Validate ``worker`` (a Tool), ``tasks`` (each a str), and
       ``max_concurrency`` (>= 1).
    2. Build one ``_WorkerInvocation`` per task, each in the same
       concurrency group; a failure is caught and reported per task, never
       raised.
    3. Aggregate the results in task order into an
       :class:`OrchestratorWorkersResult`.

References:
    - Anthropic (2024) "Building effective agents" — orchestrator-workers
    - :class:`pirn_agents.tools.agent_tool.AgentTool` (F7 agents-as-tools)
"""

from __future__ import annotations

import functools
from collections.abc import Sequence
from typing import Any, ClassVar

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator

from pirn_agents.performance.concurrency_config import ConcurrencyConfig
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.multi_agent._assemble_orchestrator_workers_result import (
    _AssembleOrchestratorWorkersResult,
)
from pirn_agents.specializations.multi_agent._worker_invocation import _WorkerInvocation
from pirn_agents.specializations.multi_agent.orchestrator_workers_result import (
    OrchestratorWorkersResult,
)
from pirn_agents.tools.tool_factory import ToolFactory


class OrchestratorWorkers(AgentPipeline):
    """Dynamically spawn one bounded worker per task, via F7 agents-as-tools."""

    _concurrency_group: ClassVar[str] = "orchestrator_workers"

    def __init__(
        self,
        *,
        tasks: Knot | Sequence[str],
        worker: Knot | Any,
        max_concurrency: Knot | int = ConcurrencyConfig.max_concurrency,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        # Read by `_inner_concurrency` after `process()` recomputes them for
        # this run; initialised here only so the attributes exist before the
        # first `process()` call (mirrors `MapAgent.__init__`).
        self._mutable_live_workers = 0
        self._mutable_max_concurrency = 1
        super().__init__(
            tasks=tasks,
            worker=worker,
            max_concurrency=max_concurrency,
            _config=_config,
            **kwargs,
        )

    def _inner_concurrency(self) -> ConcurrencyLimits | None:
        """The worker group's cap, or ``None`` when nothing runs.

        Read by ``SubTapestry._run_inner`` after ``process()`` has already
        set ``self._mutable_live_workers`` / ``self._mutable_max_concurrency``
        — the same "compute during process(), consult after" ordering
        ``MapAgent._inner_concurrency`` uses.
        """
        if self._mutable_live_workers <= 0:
            return None
        return ConcurrencyLimits(groups={self._concurrency_group: self._mutable_max_concurrency})

    async def process(
        self,
        tasks: Sequence[str],
        worker: ToolFactory,
        max_concurrency: int = ConcurrencyConfig.max_concurrency,
        **_: Any,
    ) -> Knot:
        """Fan out workers over ``tasks`` and return the aggregating sink knot.

        Args:
            tasks: The task-list items; worker count scales with its length.
            worker: The F7 agent-as-tool (or any :class:`Tool`) each task runs on.
            max_concurrency: Upper bound on simultaneously running workers;
                defaults to the shared :class:`~pirn_agents.performance.concurrency_config.ConcurrencyConfig`
                posture.

        Returns:
            The sink knot whose output is an :class:`OrchestratorWorkersResult`.

        Raises:
            TypeError: If ``worker`` is not a Tool or any task is not a str.
            ValueError: If ``max_concurrency`` is less than 1.
        """
        try:
            worker = ToolFactory.of(worker)
        except TypeError as exc:
            raise TypeError(
                f"OrchestratorWorkers: worker must be a Tool, got {type(worker).__name__}"
            ) from exc
        task_tuple = tuple(tasks)
        for index, task in enumerate(task_tuple):
            if not isinstance(task, str):
                raise TypeError(
                    f"OrchestratorWorkers: tasks[{index}] must be a str, got {type(task).__name__}"
                )
        if not isinstance(max_concurrency, int) or max_concurrency < 1:
            raise ValueError(
                f"OrchestratorWorkers: max_concurrency must be >= 1, got {max_concurrency!r}"
            )
        self._mutable_live_workers = len(task_tuple)
        self._mutable_max_concurrency = max_concurrency
        if not task_tuple:
            return Parameter(
                "orchestrator_workers_result",
                OrchestratorWorkersResult,
                default=OrchestratorWorkersResult(results=(), succeeded=0, total=0),
                _config=KnotConfig(id="orchestrator_workers_result"),
            )

        parents: dict[str, Knot] = {}
        order: list[tuple[str, str]] = []
        for index, task in enumerate(task_tuple):
            key = f"worker_{index}"
            parents[key] = _WorkerInvocation(
                task=task,
                worker=worker,
                _config=KnotConfig(id=key, concurrency_group=self._concurrency_group),
            )
            order.append((key, task))
        return Aggregator(
            combine=functools.partial(_AssembleOrchestratorWorkersResult.combine, order),
            _config=KnotConfig(id="orchestrator_workers_result"),
            **parents,
        )
