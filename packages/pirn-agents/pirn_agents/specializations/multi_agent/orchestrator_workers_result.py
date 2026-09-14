"""``OrchestratorWorkersResult`` — the aggregate of a dynamic worker fan-out."""

from __future__ import annotations

from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.multi_agent.orchestrator_workers_frame import (
    OrchestratorWorkersFrame,
)
from pirn_agents.specializations.multi_agent.worker_task_result import WorkerTaskResult


class OrchestratorWorkersResult(
    AgentResult[OrchestratorWorkersFrame, tuple[WorkerTaskResult, ...]]
):
    """Aggregate outcome of an orchestrator-workers run.

    ``OrchestratorWorkersResult`` is
    ``Payload[OrchestratorWorkersFrame, tuple[WorkerTaskResult, ...]]``
    (PIR-868, following the ADR agents-speaks-core WS6b pattern) — ``data``
    is the per-task results in task-list order, and ``metadata`` is the
    :class:`OrchestratorWorkersFrame` carrying the succeeded/total counts.
    The constructor takes the pattern's named fields (``results``, ``succeeded``,
    ``total``); read them back as ``data`` and ``metadata.<field>``.
    """

    def __init__(self, results: tuple[WorkerTaskResult, ...], succeeded: int, total: int) -> None:
        frame = OrchestratorWorkersFrame(succeeded=succeeded, total=total)
        super().__init__(metadata=frame, data=tuple(results))

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["results"] = self._audit_forms(self.data)
        return audit
