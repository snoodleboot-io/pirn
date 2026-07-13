"""``CircuitBreaker`` — a per-endpoint closed/open/half-open state machine.

The breaker guards calls to a single endpoint. In CLOSED it lets calls through
and counts consecutive failures; hitting ``failure_threshold`` trips it OPEN. In
OPEN every call fails fast with :class:`CircuitOpenError` — no network call is
attempted — until ``cooldown_seconds`` elapse, at which point the next call
enters HALF_OPEN. In HALF_OPEN a bounded number of trial calls run: reaching
``success_threshold`` consecutive successes closes the breaker, while a single
failure re-opens it and restarts the cooldown.

All state mutation is serialised behind an :class:`asyncio.Lock`, so concurrent
callers sharing one breaker observe a consistent state machine. The wall clock
is injected (defaulting to :func:`time.monotonic`) so tests drive transitions
deterministically without real sleeps.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from pirn_agents.resilience.circuit_breaker_config import CircuitBreakerConfig
from pirn_agents.resilience.circuit_open_error import CircuitOpenError
from pirn_agents.resilience.circuit_state import CircuitState


class CircuitBreaker:
    """A single endpoint's closed/open/half-open breaker, async-safe."""

    def __init__(
        self,
        config: CircuitBreakerConfig,
        *,
        endpoint: str = "default",
        clock: Callable[[], float] | None = None,
    ) -> None:
        """Build a breaker for one endpoint.

        Args:
            config: Threshold/cooldown tuning.
            endpoint: Stable identity used in :class:`CircuitOpenError`.
            clock: Zero-arg monotonic clock; defaults to :func:`time.monotonic`.
                Injected in tests for deterministic transitions.

        Raises:
            TypeError: If ``config`` is not a :class:`CircuitBreakerConfig`.
        """
        if not isinstance(config, CircuitBreakerConfig):
            raise TypeError(
                f"CircuitBreaker: config must be a CircuitBreakerConfig, "
                f"got {type(config).__name__}"
            )
        self._config = config
        self._endpoint = endpoint
        self._clock = clock if clock is not None else time.monotonic
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._half_open_successes = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def config(self) -> CircuitBreakerConfig:
        """The config this breaker was built from."""
        return self._config

    @property
    def endpoint(self) -> str:
        """The endpoint identity this breaker guards."""
        return self._endpoint

    @property
    def state(self) -> CircuitState:
        """The current raw state (no cooldown transition is applied on read)."""
        return self._state

    async def acquire(self) -> None:
        """Admit one call, or fail fast if the breaker is open.

        Applies the OPEN→HALF_OPEN cooldown transition when due. In OPEN before
        the cooldown elapses, raises without attempting any call.

        Raises:
            CircuitOpenError: If the breaker is OPEN and the cooldown has not yet
                elapsed.
        """
        async with self._lock:
            if self._state is CircuitState.OPEN:
                opened_at = self._opened_at if self._opened_at is not None else self._clock()
                retry_at = opened_at + self._config.cooldown_seconds
                if self._clock() < retry_at:
                    raise CircuitOpenError(self._endpoint, retry_at=retry_at)
                self._state = CircuitState.HALF_OPEN
                self._half_open_successes = 0

    async def record_success(self) -> None:
        """Record a successful call, closing the breaker when trials pass."""
        async with self._lock:
            if self._state is CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self._config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._consecutive_failures = 0
                    self._half_open_successes = 0
                    self._opened_at = None
            else:
                self._consecutive_failures = 0

    async def record_failure(self) -> None:
        """Record a failed call, tripping or re-opening the breaker as needed."""
        async with self._lock:
            if self._state is CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()
                self._half_open_successes = 0
                return
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._config.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()

    @asynccontextmanager
    async def guard(self) -> AsyncIterator[None]:
        """Guard the ``async with`` body: fail fast when open, else record.

        Acquires admission on entry (raising :class:`CircuitOpenError` if open),
        records a failure if the body raises, and records a success otherwise.

        Raises:
            CircuitOpenError: If the breaker rejects the call on entry.
        """
        await self.acquire()
        try:
            yield
        except Exception:
            await self.record_failure()
            raise
        await self.record_success()
