"""``OrchestratorWorkersFrame`` — lineage metadata for an :class:`OrchestratorWorkersResult`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class OrchestratorWorkersFrame(PirnOpaqueValue):
    """Run-level counts for an orchestrator-workers fan-out.

    The frame half of the
    ``Payload[OrchestratorWorkersFrame, tuple[WorkerTaskResult, ...]]`` split
    (PIR-868).

    Attributes
    ----------
    succeeded:
        Count of tasks whose worker returned a successful result.
    total:
        Total number of tasks dispatched (equals ``len(results)``).
    """

    succeeded: int
    total: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"succeeded": self.succeeded, "total": self.total}
