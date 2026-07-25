"""``FailoverChain`` — try ordered candidates until one succeeds.

Walks an ordered list of :class:`FailoverCandidate` values, returning the first
that produces a value. A candidate is *skipped* (no call attempted) when its
circuit breaker is open; otherwise it runs under its own optional timeout. On a
raised exception or a timeout the chain records the reason and falls through to
the next candidate, feeding the outcome back into the candidate's breaker so a
repeatedly failing endpoint trips and is skipped on later runs.

This is the resilience counterpart to F8's confidence-ordered routing
``FallbackChain``: that one reroutes on *low confidence* over routed tools, this
one reroutes on *error / timeout / open circuit* over provider candidates. The
run's trace is returned as a :class:`FailoverResult` so callers see which
candidates were attempted and why each earlier one fell through.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from pirn_agents.resilience.circuit_breaker_registry import CircuitBreakerRegistry
from pirn_agents.resilience.circuit_open_error import CircuitOpenError
from pirn_agents.resilience.failover_attempt import FailoverAttempt
from pirn_agents.resilience.failover_candidate import FailoverCandidate
from pirn_agents.resilience.failover_outcome import FailoverOutcome
from pirn_agents.resilience.failover_result import FailoverResult


class FailoverChain:
    """Invoke an ordered candidate chain, rerouting on failure/timeout/open."""

    def __init__(
        self,
        candidates: Sequence[FailoverCandidate],
        *,
        breakers: CircuitBreakerRegistry | None = None,
    ) -> None:
        """Build the chain.

        Args:
            candidates: Ordered candidates, tried front-to-back until one wins.
                Must be non-empty and hold only :class:`FailoverCandidate`.
            breakers: Optional registry consulted per candidate; when present, an
                open candidate is skipped and each attempt's outcome is recorded
                into its breaker. When ``None``, no circuit logic is applied.

        Raises:
            ValueError: If ``candidates`` is empty.
            TypeError: If an entry is not a :class:`FailoverCandidate` or
                ``breakers`` is not a :class:`CircuitBreakerRegistry`.
        """
        ordered = tuple(candidates)
        if not ordered:
            raise ValueError("FailoverChain: candidates must be non-empty")
        for index, candidate in enumerate(ordered):
            if not isinstance(candidate, FailoverCandidate):
                raise TypeError(
                    f"FailoverChain: candidates[{index}] must be a FailoverCandidate, "
                    f"got {type(candidate).__name__}"
                )
        if breakers is not None and not isinstance(breakers, CircuitBreakerRegistry):
            raise TypeError(
                f"FailoverChain: breakers must be a CircuitBreakerRegistry or None, "
                f"got {type(breakers).__name__}"
            )
        self._candidates = ordered
        self._breakers = breakers

    async def run(self) -> FailoverResult:
        """Walk the chain, returning the first success or an exhausted result.

        Returns:
            A :class:`FailoverResult` whose ``attempts`` trace records every
            candidate considered, in order.
        """
        attempts: list[FailoverAttempt] = []
        for candidate in self._candidates:
            breaker = self._breakers.get(candidate.name) if self._breakers is not None else None
            if breaker is not None:
                try:
                    await breaker.acquire()
                except CircuitOpenError:
                    attempts.append(
                        FailoverAttempt(
                            candidate.name, FailoverOutcome.CIRCUIT_OPEN, "circuit_open"
                        )
                    )
                    continue
            try:
                if candidate.timeout is not None:
                    async with asyncio.timeout(candidate.timeout):
                        value = await candidate.operation()
                else:
                    value = await candidate.operation()
            except TimeoutError:
                if breaker is not None:
                    await breaker.record_failure()
                attempts.append(FailoverAttempt(candidate.name, FailoverOutcome.TIMEOUT, "timeout"))
                continue
            except Exception as exc:
                if breaker is not None:
                    await breaker.record_failure()
                attempts.append(FailoverAttempt(candidate.name, FailoverOutcome.ERROR, str(exc)))
                continue
            if breaker is not None:
                await breaker.record_success()
            attempts.append(FailoverAttempt(candidate.name, FailoverOutcome.SUCCESS, None))
            return FailoverResult(
                succeeded=True,
                chosen=candidate.name,
                value=value,
                attempts=tuple(attempts),
            )
        return FailoverResult(
            succeeded=False,
            chosen=None,
            value=None,
            attempts=tuple(attempts),
        )
