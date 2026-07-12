"""``OrchestratorWorkersResult`` — the aggregate of a dynamic worker fan-out."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.specializations.multi_agent.worker_task_result import WorkerTaskResult


@dataclass(frozen=True)
class OrchestratorWorkersResult(PirnOpaqueValue):
    """Aggregate outcome of an orchestrator-workers run.

    Attributes
    ----------
    results:
        Per-task results in task-list order.
    succeeded:
        Count of tasks whose worker returned a successful result.
    total:
        Total number of tasks dispatched (equals ``len(results)``).
    """

    results: tuple[WorkerTaskResult, ...]
    succeeded: int
    total: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "results": [item._pirn_audit_dict() for item in self.results],
            "succeeded": self.succeeded,
            "total": self.total,
        }
