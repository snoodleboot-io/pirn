"""``CircuitClosedCheck`` — admit a failover candidate only while its breaker allows a call."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.check import Check

from pirn_agents.resilience.circuit_breaker_registry import CircuitBreakerRegistry
from pirn_agents.resilience.circuit_open_error import CircuitOpenError
from pirn_agents.resilience.failover_attempt import FailoverAttempt
from pirn_agents.resilience.failover_candidate import FailoverCandidate


class CircuitClosedCheck(Check):
    """``True`` when the candidate's breaker admits a call, ``False`` when it is open.

    The ``check`` of the ``Gate`` in front of a candidate's call: an open
    circuit closes the gate, so the call knot is skipped without running and
    its skip carries :attr:`FailoverAttempt.circuit_open_reason`.
    """

    skip_reason: ClassVar[str | None] = FailoverAttempt.circuit_open_reason

    def __init__(
        self,
        *,
        candidate: Knot | FailoverCandidate,
        breakers: Knot | CircuitBreakerRegistry,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(candidate=candidate, breakers=breakers, _config=_config, **kwargs)

    async def process(
        self, candidate: FailoverCandidate, breakers: CircuitBreakerRegistry, **_: Any
    ) -> bool:
        """Acquire the candidate's breaker.

        Args:
            candidate: The candidate about to be called.
            breakers: The registry holding its breaker.

        Returns:
            ``True`` when the breaker admitted the call, ``False`` when it is open.
        """
        try:
            await breakers.get(candidate.name).acquire()
        except CircuitOpenError:
            return False
        return True
