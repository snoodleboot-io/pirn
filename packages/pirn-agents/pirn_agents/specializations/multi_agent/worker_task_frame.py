"""``WorkerTaskFrame`` — lineage metadata for a :class:`WorkerTaskResult`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class WorkerTaskFrame(PirnOpaqueValue):
    """Run-level context for one orchestrator-workers task dispatch.

    The frame half of the ``Payload[WorkerTaskFrame, ToolResult]`` split
    (PIR-868).

    Attributes
    ----------
    task:
        The task string handed to the worker.
    """

    task: str

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"task": self.task}
