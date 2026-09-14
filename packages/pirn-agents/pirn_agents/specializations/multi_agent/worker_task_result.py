"""``WorkerTaskResult`` — one task's outcome in an orchestrator-workers run."""

from __future__ import annotations

from typing import Any

from pirn_agents.specializations.base.agent_result import AgentResult
from pirn_agents.specializations.multi_agent.worker_task_frame import WorkerTaskFrame
from pirn_agents.tools.tool_result import ToolResult


class WorkerTaskResult(AgentResult[WorkerTaskFrame, ToolResult]):
    """The result of dispatching one task-list item to a worker.

    ``WorkerTaskResult`` is ``Payload[WorkerTaskFrame, ToolResult]``
    (PIR-868, following the ADR agents-speaks-core WS6b pattern) — ``data``
    is the :class:`ToolResult` the worker (an F7 agent-as-tool) returned,
    and ``metadata`` is the :class:`WorkerTaskFrame` carrying the task
    string. The pre-ADR field names (``task``, ``result``) stay available as
    read-only properties, so every existing construction and
    attribute-access call site keeps compiling unchanged.
    """

    def __init__(self, task: str, result: ToolResult) -> None:
        frame = WorkerTaskFrame(task=task)
        super().__init__(metadata=frame, data=result)

    @property
    def task(self) -> str:
        return self._metadata.task

    @property
    def result(self) -> ToolResult:
        return self._data

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(self._metadata._pirn_audit_dict())
        audit["result"] = self.result._pirn_audit_dict()
        return audit
