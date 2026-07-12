"""``WorkerTaskResult`` — one task's outcome in an orchestrator-workers run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.types.tool_result import ToolResult


@dataclass(frozen=True)
class WorkerTaskResult(PirnOpaqueValue):
    """The result of dispatching one task-list item to a worker.

    Attributes
    ----------
    task:
        The task string handed to the worker.
    result:
        The :class:`ToolResult` the worker (an F7 agent-as-tool) returned.
    """

    task: str
    result: ToolResult

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"task": self.task, "result": self.result._pirn_audit_dict()}
