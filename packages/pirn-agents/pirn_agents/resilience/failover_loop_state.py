"""``FailoverLoopState`` — the value :class:`FailoverLoop` threads between attempts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.resilience.circuit_breaker_registry import CircuitBreakerRegistry
from pirn_agents.resilience.failover_candidate import FailoverCandidate
from pirn_agents.resilience.failover_result import FailoverResult


@dataclass(frozen=True)
class FailoverLoopState(PirnOpaqueValue):
    """A failover chain's inputs plus the trace accumulated so far.

    The loop reads the candidates and breakers of a run from its state, not
    from instance attributes, so they travel through the graph as a value
    (knot-design-rules.md Rule 4).

    Attributes:
        candidates: The ordered candidates, tried front to back.
        breakers: The circuit-breaker registry consulted per candidate, or
            ``None`` for no circuit logic.
        result: The trace accumulated so far.
    """

    candidates: tuple[FailoverCandidate, ...]
    breakers: CircuitBreakerRegistry | None
    result: FailoverResult

    def next_candidate(self) -> FailoverCandidate | None:
        """The candidate the next attempt runs, or ``None`` once succeeded or exhausted."""
        index = len(self.result.attempts)
        if self.result.succeeded or index >= len(self.candidates):
            return None
        return self.candidates[index]

    @staticmethod
    def _audit(value: PirnOpaqueValue) -> Any:
        """Audit a child through the ``PirnOpaqueValue`` contract it shares with this value."""
        return value._pirn_audit_dict()

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "candidates": [candidate.name for candidate in self.candidates],
            "circuit_breakers": self.breakers is not None,
            "result": self._audit(self.result),
        }
