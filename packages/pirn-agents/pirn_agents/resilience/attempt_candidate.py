"""``AttemptCandidate`` — fold one failover candidate's call outcome into the trace."""

from __future__ import annotations

from typing import Any

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.skipped import Skipped

from pirn_agents.resilience.circuit_breaker_registry import CircuitBreakerRegistry
from pirn_agents.resilience.failover_attempt import FailoverAttempt
from pirn_agents.resilience.failover_candidate import FailoverCandidate
from pirn_agents.resilience.failover_result import FailoverResult


class AttemptCandidate(Knot):
    """Fold a :class:`CandidateCall`'s ``Result`` into the chain's accumulated result.

    Wired with ``error_policy=RECEIVE_ERRORS`` so ``outcome`` is the call's raw
    ``Ok``/``Err``/``Skipped``. An ``Ok`` and an ``Err`` (a raised exception, or
    the engine's ``KnotTimeoutError`` for a call that outlived the candidate's
    ``KnotConfig.timeout``) are recorded into the candidate's breaker; a
    ``Skipped`` call (its circuit was open) made no call and records nothing.
    """

    def __init__(
        self,
        *,
        prior: Knot | FailoverResult,
        candidate: Knot | FailoverCandidate,
        breakers: Knot | CircuitBreakerRegistry | None,
        outcome: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prior=prior,
            candidate=candidate,
            breakers=breakers,
            outcome=outcome,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        prior: FailoverResult,
        candidate: FailoverCandidate,
        breakers: CircuitBreakerRegistry | None,
        outcome: Ok[Any] | Err | Skipped,
        **_: Any,
    ) -> FailoverResult:
        """Append ``candidate``'s attempt to ``prior``.

        Args:
            prior: The chain's accumulated result before this candidate.
            candidate: The candidate that was attempted.
            breakers: The circuit-breaker registry, or ``None``.
            outcome: The candidate call's ``Result``.

        Returns:
            A new :class:`FailoverResult` with this attempt appended; succeeded,
            with the call's value, when ``outcome`` is ``Ok``.
        """
        breaker = breakers.get(candidate.name) if breakers is not None else None
        if isinstance(outcome, Skipped):
            attempt = FailoverAttempt(candidate.name, Skipped(reason=outcome.reason))
            return FailoverResult(
                succeeded=False,
                chosen=None,
                value=None,
                attempts=(*prior.attempts, attempt),
            )
        if isinstance(outcome, Err):
            if breaker is not None:
                await breaker.record_failure()
            return FailoverResult(
                succeeded=False,
                chosen=None,
                value=None,
                attempts=(*prior.attempts, FailoverAttempt(candidate.name, outcome)),
            )
        if breaker is not None:
            await breaker.record_success()
        return FailoverResult(
            succeeded=True,
            chosen=candidate.name,
            value=outcome.value,
            attempts=(*prior.attempts, FailoverAttempt(candidate.name, outcome)),
        )
