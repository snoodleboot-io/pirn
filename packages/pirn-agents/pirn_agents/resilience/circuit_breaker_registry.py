"""``CircuitBreakerRegistry`` — one breaker per endpoint/key, lazily created."""

from __future__ import annotations

from collections.abc import Callable

from pirn_agents.resilience.circuit_breaker import CircuitBreaker
from pirn_agents.resilience.circuit_breaker_config import CircuitBreakerConfig


class CircuitBreakerRegistry:
    """Scopes circuit-breaker state per endpoint/key.

    Each distinct endpoint key gets its own :class:`CircuitBreaker`, built lazily
    on first use from a shared :class:`CircuitBreakerConfig`, so a dead backend
    trips only its own breaker and never suppresses calls to healthy peers.
    Lookup-or-create is synchronous and does not ``await`` between the membership
    check and the insert, so under cooperative scheduling no two coroutines can
    race to build two breakers for the same key.
    """

    def __init__(
        self,
        config: CircuitBreakerConfig,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        """Build the registry.

        Args:
            config: Shared config every per-endpoint breaker is built from.
            clock: Optional monotonic clock passed to each breaker; injected in
                tests for deterministic transitions.

        Raises:
            TypeError: If ``config`` is not a :class:`CircuitBreakerConfig`.
        """
        if not isinstance(config, CircuitBreakerConfig):
            raise TypeError(
                f"CircuitBreakerRegistry: config must be a CircuitBreakerConfig, "
                f"got {type(config).__name__}"
            )
        self._config = config
        self._clock = clock
        self._breakers: dict[str, CircuitBreaker] = {}

    def get(self, endpoint: str) -> CircuitBreaker:
        """Return the breaker for ``endpoint``, creating it on first request."""
        breaker = self._breakers.get(endpoint)
        if breaker is None:
            breaker = CircuitBreaker(self._config, endpoint=endpoint, clock=self._clock)
            self._breakers[endpoint] = breaker
        return breaker

    def endpoints(self) -> tuple[str, ...]:
        """The endpoint keys that currently have a live breaker."""
        return tuple(self._breakers)
