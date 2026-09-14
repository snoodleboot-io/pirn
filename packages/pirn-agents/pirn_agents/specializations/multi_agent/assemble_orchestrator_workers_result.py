"""``AssembleOrchestratorWorkersResult`` — Aggregator ``combine`` target."""

from __future__ import annotations

from pirn_agents.specializations.multi_agent.orchestrator_workers_result import (
    OrchestratorWorkersResult,
)
from pirn_agents.specializations.multi_agent.worker_task_result import WorkerTaskResult
from pirn_agents.tools.tool_result import ToolResult


class AssembleOrchestratorWorkersResult:
    """Aggregator ``combine`` target: reassemble the ordered outcome."""

    @staticmethod
    def combine(
        order: list[tuple[str, str]], **task_results: ToolResult
    ) -> OrchestratorWorkersResult:
        """Rebuild the ordered :class:`OrchestratorWorkersResult`.

        Args:
            order: ``(parent_kwarg_key, task)`` pairs in task-list order.
            **task_results: One :class:`ToolResult` per parent kwarg key.

        Returns:
            The aggregate outcome, in task-list order.
        """
        results = tuple(
            WorkerTaskResult(task=task, result=task_results[key]) for key, task in order
        )
        succeeded = sum(1 for item in results if item.result.succeeded)
        return OrchestratorWorkersResult(results=results, succeeded=succeeded, total=len(results))
