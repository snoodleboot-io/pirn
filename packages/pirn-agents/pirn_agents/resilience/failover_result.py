"""``FailoverResult`` — the typed outcome of a failover-chain run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.resilience.failover_attempt import FailoverAttempt


@dataclass(frozen=True)
class FailoverResult(PirnOpaqueValue):
    """Outcome of walking an ordered failover chain until one candidate wins.

    The ``attempts`` tuple is the run's trace: one
    :class:`FailoverAttempt` per candidate considered, in order, recording
    successes, failures, timeouts, and circuit-open skips so callers can see
    exactly which candidates were tried and why each earlier one fell through.

    Attributes
    ----------
    succeeded:
        Whether some candidate returned a value.
    chosen:
        The name of the winning candidate, or ``None`` on exhaustion.
    value:
        The winning candidate's return value, or ``None`` on exhaustion. (A
        candidate that legitimately returns ``None`` still sets
        ``succeeded=True``.)
    attempts:
        Ordered trace of every candidate considered.
    """

    succeeded: bool
    chosen: str | None
    value: Any
    attempts: tuple[FailoverAttempt, ...]

    @staticmethod
    def _audit_all(values: tuple[PirnOpaqueValue, ...]) -> list[Any]:
        """Audit each child through the ``PirnOpaqueValue`` contract it shares with this value."""
        return [value._pirn_audit_dict() for value in values]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "succeeded": self.succeeded,
            "chosen": self.chosen,
            "attempts": self._audit_all(self.attempts),
        }
