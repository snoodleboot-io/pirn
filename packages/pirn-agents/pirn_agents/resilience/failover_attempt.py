"""``FailoverAttempt`` — one trace record in a failover run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.resilience.failover_outcome import FailoverOutcome


@dataclass(frozen=True)
class FailoverAttempt(PirnOpaqueValue):
    """The traced disposition of a single candidate during a failover run.

    Attributes
    ----------
    name:
        The candidate's stable identity.
    outcome:
        Why the candidate succeeded, failed, or was skipped.
    error:
        A human-readable reason for a non-success outcome (exception message,
        ``"timeout"``, or ``"circuit_open"``), or ``None`` on success.
    """

    name: str
    outcome: FailoverOutcome
    error: str | None = None

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "outcome": self.outcome.value,
            "error": self.error,
        }
