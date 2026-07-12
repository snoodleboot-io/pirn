"""``OrchestratorWorkers`` — dynamic worker fan-out over a task list via F7.

A :class:`SubTapestry` that spawns **one worker invocation per task-list item**,
bounded by a configurable ``max_concurrency`` semaphore, and aggregates the
per-task outcomes into a typed :class:`OrchestratorWorkersResult`.

The worker is any :class:`Tool` — in practice an F7
:class:`~pirn_agents.agent_tool.AgentTool` wrapping a specialist agent — so the
orchestrator reuses agents-as-tools rather than a bespoke worker abstraction. The
worker count therefore scales with the task list while wall-clock stays bounded by
the concurrency cap, exactly like the F1
:class:`~pirn_agents.parallel_tool_executor.ParallelToolExecutor`.

Algorithm:
    1. Validate ``worker`` (a Tool), ``tasks`` (each a str), and
       ``max_concurrency`` (>= 1).
    2. Fan out one ``worker.invoke({"task": task})`` per task under an
       :class:`asyncio.Semaphore`; failures are isolated per task.
    3. Aggregate the results in task order and surface them via a terminal
       :class:`Source`.

References:
    - Anthropic (2024) "Building effective agents" — orchestrator-workers
    - :class:`pirn_agents.agent_tool.AgentTool` (F7 agents-as-tools)
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.specializations.multi_agent.orchestrator_workers_result import (
    OrchestratorWorkersResult,
)
from pirn_agents.specializations.multi_agent.worker_task_result import WorkerTaskResult
from pirn_agents.tool import Tool
from pirn_agents.types.tool_result import ToolResult
from pirn_agents.types.tool_status import ToolStatus


class OrchestratorWorkers(SubTapestry):
    """Dynamically spawn one bounded worker per task, via F7 agents-as-tools."""

    def __init__(
        self,
        *,
        tasks: Knot | Sequence[str],
        worker: Knot | Tool,
        max_concurrency: Knot | int = 8,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            tasks=tasks,
            worker=worker,
            max_concurrency=max_concurrency,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        tasks: Sequence[str],
        worker: Tool,
        max_concurrency: int = 8,
        **_: Any,
    ) -> Any:
        """Fan out workers over ``tasks`` and surface an aggregate result.

        Args:
            tasks: The task-list items; worker count scales with its length.
            worker: The F7 agent-as-tool (or any :class:`Tool`) each task runs on.
            max_concurrency: Upper bound on simultaneously running workers.

        Returns:
            A terminal :class:`Source` whose output is an
            :class:`OrchestratorWorkersResult`.

        Raises:
            TypeError: If ``worker`` is not a Tool or any task is not a str.
            ValueError: If ``max_concurrency`` is less than 1.
        """
        if not isinstance(worker, Tool):
            raise TypeError(
                f"OrchestratorWorkers: worker must be a Tool, got {type(worker).__name__}"
            )
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

        semaphore = asyncio.Semaphore(max_concurrency)
        gathered = await asyncio.gather(
            *(self._run_one(worker, task, semaphore) for task in task_tuple)
        )
        results = tuple(
            WorkerTaskResult(task=task, result=result)
            for task, result in zip(task_tuple, gathered, strict=True)
        )
        succeeded = sum(1 for item in results if item.result.status is ToolStatus.OK)
        result_value = OrchestratorWorkersResult(
            results=results,
            succeeded=succeeded,
            total=len(results),
        )
        _result = result_value

        class _OrchestratorWorkersResultSource(Source):
            async def process(self, **_: Any) -> OrchestratorWorkersResult:
                return _result

        return _OrchestratorWorkersResultSource(
            _config=KnotConfig(id="orchestrator_workers_result")
        )

    @staticmethod
    async def _run_one(worker: Tool, task: str, semaphore: asyncio.Semaphore) -> ToolResult:
        """Invoke the worker for one task under the semaphore, never raising."""
        async with semaphore:
            try:
                raw = await worker.invoke({"task": task})
            except Exception as exc:
                return ToolResult(call_id=task, result=None, error=str(exc))
        if isinstance(raw, ToolResult):
            return raw
        return ToolResult(call_id=task, result=raw, status=ToolStatus.OK)
