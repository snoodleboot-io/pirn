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

The chain is expressed as a graph rather than a hand-rolled
``for candidate in candidates`` loop: ``candidates`` is a resolved value known
in full by the time ``process()`` runs, so its length is not data-dependent —
unlike an agentic loop, no ``LoopSubTapestry`` is needed. Instead ``process()``
builds a static chain of one :class:`_AttemptCandidate` knot per candidate,
each taking the previous candidate's accumulated :class:`FailoverResult` as its
``prior`` parent and folding its own outcome into it. A candidate whose
``prior`` already succeeded returns it unchanged without calling its own
``operation`` — the actual (paid) call is skipped exactly as before, and every
candidate still gets its own engine ``Result``, history record, and lineage
(where the original hid all of them behind one knot's hand-rolled loop).

Algorithm:
    1. Validate ``candidates`` (non-empty, all :class:`FailoverCandidate`) and
       ``breakers`` (a :class:`CircuitBreakerRegistry` or ``None``).
    2. Build the initial (unattempted, unsucceeded) :class:`FailoverResult`.
    3. Chain one :class:`_AttemptCandidate` per candidate: each checks whether
       the accumulated result already succeeded (pass through unchanged), else
       consults the candidate's circuit breaker (skip on open), runs the
       operation under its optional timeout, records the outcome into the
       breaker, and appends a :class:`FailoverAttempt` to the trace.
    4. The final knot's accumulated :class:`FailoverResult` is the chain's
       output.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.resilience.circuit_breaker_registry import CircuitBreakerRegistry
from pirn_agents.resilience.circuit_open_error import CircuitOpenError
from pirn_agents.resilience.failover_attempt import FailoverAttempt
from pirn_agents.resilience.failover_candidate import FailoverCandidate
from pirn_agents.resilience.failover_outcome import FailoverOutcome
from pirn_agents.resilience.failover_result import FailoverResult
from pirn_agents.specializations.base.resolved_value_knot import ResolvedValueKnot


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


class FailoverChain(SubTapestry):
    """Invoke an ordered candidate chain, rerouting on failure/timeout/open."""

    def __init__(
        self,
        *,
        candidates: Knot | Sequence[FailoverCandidate],
        breakers: Knot | CircuitBreakerRegistry | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        """Wire the chain's inputs.

        Args:
            candidates: Ordered candidates, tried front-to-back until one wins.
            breakers: Optional registry consulted per candidate.
            _config: Knot configuration carrying this chain's graph id.
            **kwargs: Forwarded to :class:`~pirn.nodes.sub_tapestry.SubTapestry`.
        """
        super().__init__(candidates=candidates, breakers=breakers, _config=_config, **kwargs)

    async def process(
        self,
        candidates: Sequence[FailoverCandidate],
        # `breakers` is typed `Any` here (not `CircuitBreakerRegistry | None`):
        # CircuitBreakerRegistry is a plain class, not a PirnOpaqueValue, and
        # pydantic has no schema for it. `Knot.__init__` builds a `TypeAdapter`
        # for every declared `process()` input eagerly, so a concrete
        # annotation raises `PydanticSchemaGenerationError` at construction
        # time, before this method ever runs its own isinstance check below.
        breakers: Any = None,
        **_: Any,
    ) -> Knot:
        """Build the candidate chain and return its accumulating sink knot.

        Args:
            candidates: Ordered candidates, tried front-to-back until one wins.
                Must be non-empty and hold only :class:`FailoverCandidate`.
            breakers: Optional :class:`CircuitBreakerRegistry` consulted per
                candidate; when present, an open candidate is skipped and each
                attempt's outcome is recorded into its breaker. When ``None``,
                no circuit logic is applied.

        Returns:
            The sink knot whose output is the :class:`FailoverResult` trace.

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

        chain: Knot = ResolvedValueKnot(
            value=FailoverResult(succeeded=False, chosen=None, value=None, attempts=()),
            _config=KnotConfig(id="initial"),
        )
        for index, candidate in enumerate(ordered):
            chain = _AttemptCandidate(
                prior=chain,
                candidate=candidate,
                breakers=breakers,
                _config=KnotConfig(id=f"attempt_{index}"),
            )
        return chain
