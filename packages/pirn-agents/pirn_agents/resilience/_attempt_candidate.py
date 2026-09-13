"""``_AttemptCandidate`` — fold one failover candidate's outcome into state."""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.resilience.circuit_open_error import CircuitOpenError
from pirn_agents.resilience.failover_attempt import FailoverAttempt
from pirn_agents.resilience.failover_candidate import FailoverCandidate
from pirn_agents.resilience.failover_outcome import FailoverOutcome
from pirn_agents.resilience.failover_result import FailoverResult


class _AttemptCandidate(Knot):
    """Fold one candidate's outcome into the chain's accumulated result.

    ``breakers`` is typed ``Any``, justified: :class:`CircuitBreakerRegistry`
    is a plain class rather than a :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`,
    and pydantic has no schema for it — ``Knot.__init__`` builds a
    ``TypeAdapter`` for every declared input eagerly, so a concrete
    ``CircuitBreakerRegistry`` annotation raises
    ``PydanticSchemaGenerationError`` at construction time. This mirrors why
    the pre-remediation version of this file stored ``breakers`` on a
    ``_mutable_`` slot instead of wiring it through ``super().__init__()`` at
    all.
    """

    def __init__(
        self,
        *,
        prior: Knot | FailoverResult,
        candidate: Knot | FailoverCandidate,
        breakers: Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prior=prior, candidate=candidate, breakers=breakers, _config=_config, **kwargs
        )

    async def process(
        self,
        prior: FailoverResult,
        candidate: FailoverCandidate,
        breakers: Any,
        **_: Any,
    ) -> FailoverResult:
        """Fold ``candidate``'s outcome into ``prior``.

        Args:
            prior: The chain's accumulated result before this candidate.
            candidate: This candidate's name, operation, and optional timeout.
            breakers: The circuit-breaker registry, or ``None`` to apply no
                circuit logic.

        Returns:
            ``prior`` unchanged if it already succeeded; otherwise a new
            :class:`FailoverResult` with this candidate's attempt appended,
            and ``succeeded=True`` if this candidate's operation returned.
        """
        if prior.succeeded:
            return prior
        attempts = (*prior.attempts,)
        breaker = breakers.get(candidate.name) if breakers is not None else None
        if breaker is not None:
            try:
                await breaker.acquire()
            except CircuitOpenError:
                return FailoverResult(
                    succeeded=False,
                    chosen=None,
                    value=None,
                    attempts=(
                        *attempts,
                        FailoverAttempt(
                            candidate.name, FailoverOutcome.CIRCUIT_OPEN, "circuit_open"
                        ),
                    ),
                )
        try:
            if candidate.timeout is not None:
                async with asyncio.timeout(candidate.timeout):
                    value = await candidate.operation()
            else:
                value = await candidate.operation()
        except TimeoutError:
            if breaker is not None:
                await breaker.record_failure()
            return FailoverResult(
                succeeded=False,
                chosen=None,
                value=None,
                attempts=(
                    *attempts,
                    FailoverAttempt(candidate.name, FailoverOutcome.TIMEOUT, "timeout"),
                ),
            )
        except Exception as exc:
            if breaker is not None:
                await breaker.record_failure()
            return FailoverResult(
                succeeded=False,
                chosen=None,
                value=None,
                attempts=(
                    *attempts,
                    FailoverAttempt(candidate.name, FailoverOutcome.ERROR, str(exc)),
                ),
            )
        if breaker is not None:
            await breaker.record_success()
        return FailoverResult(
            succeeded=True,
            chosen=candidate.name,
            value=value,
            attempts=(*attempts, FailoverAttempt(candidate.name, FailoverOutcome.SUCCESS, None)),
        )
