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
    string. The constructor takes the pattern's named fields (``task``, ``result``); read
    them back as ``metadata.task`` and ``data``.
    """

    def __init__(self, task: str, result: ToolResult) -> None:
        frame = WorkerTaskFrame(task=task)
        super().__init__(metadata=frame, data=result)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["result"] = self._audit_form(self.data)
        return audit
