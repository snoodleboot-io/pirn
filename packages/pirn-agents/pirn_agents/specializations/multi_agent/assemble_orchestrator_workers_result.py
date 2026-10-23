"""``AssembleOrchestratorWorkersResult`` — Aggregator ``combine`` target."""

from __future__ import annotations

from pirn_agents.specializations.multi_agent.orchestrator_workers_result import (
    OrchestratorWorkersResult,
)
from pirn_agents.specializations.multi_agent.worker_task_result import WorkerTaskResult


class AssembleOrchestratorWorkersResult:
    """Aggregator ``combine`` target: reassemble the ordered outcome."""

    @staticmethod
    def combine(
        order: list[tuple[str, str]], **task_results: WorkerTaskResult
    ) -> OrchestratorWorkersResult:
        """Rebuild the ordered :class:`OrchestratorWorkersResult`.

        Args:
            order: ``(parent_kwarg_key, task)`` pairs in task-list order.
            **task_results: One :class:`WorkerTaskResult` per parent kwarg key —
                each :class:`WorkerInvocation` already names its task (PIR-874).

        Returns:
            The aggregate outcome, in task-list order.
        """
        results = tuple(task_results[key] for key, _task in order)
        succeeded = sum(1 for item in results if item.data.succeeded)
        return OrchestratorWorkersResult(results=results, succeeded=succeeded, total=len(results))
