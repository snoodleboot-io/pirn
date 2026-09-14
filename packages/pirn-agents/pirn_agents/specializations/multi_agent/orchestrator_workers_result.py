"""``OrchestratorWorkersResult`` — the aggregate of a dynamic worker fan-out."""

from __future__ import annotations

from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

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
    The pre-ADR field names (``results``, ``succeeded``, ``total``) stay
    available as read-only properties, so every existing construction and
    attribute-access call site keeps compiling unchanged.
    """

    def __init__(self, results: tuple[WorkerTaskResult, ...], succeeded: int, total: int) -> None:
        frame = OrchestratorWorkersFrame(succeeded=succeeded, total=total)
        super().__init__(metadata=frame, data=tuple(results))

    @property
    def results(self) -> tuple[WorkerTaskResult, ...]:
        return self._data

    @property
    def succeeded(self) -> int:
        return self._metadata.succeeded

    @property
    def total(self) -> int:
        return self._metadata.total

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        results: tuple[PirnOpaqueValue, ...] = self.results
        audit["results"] = [item._pirn_audit_dict() for item in results]
        return audit
