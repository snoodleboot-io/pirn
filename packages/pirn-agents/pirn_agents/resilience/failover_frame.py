"""``FailoverFrame`` — lineage metadata for a :class:`FailoverResult`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn_agents.resilience.failover_attempt import FailoverAttempt
from pirn_agents.specializations.base.nested_audit_value import NestedAuditValue


@dataclass(frozen=True)
class FailoverFrame(NestedAuditValue):
    """Run-level facts for a failover-chain walk.

    The frame half of the ``Payload[FailoverFrame, Any]`` split (PIR-868,
    PIR-874); the winning candidate's return value is the ``data`` half.

    Attributes
    ----------
    succeeded:
        Whether some candidate returned a value.
    chosen:
        The name of the winning candidate, or ``None`` on exhaustion.
    attempts:
        Ordered trace of every candidate considered: successes, failures,
        timeouts and circuit-open skips.
    """

    succeeded: bool
    chosen: str | None
    attempts: tuple[FailoverAttempt, ...]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "succeeded": self.succeeded,
            "chosen": self.chosen,
            "attempts": self._audit_forms(self.attempts),
        }
