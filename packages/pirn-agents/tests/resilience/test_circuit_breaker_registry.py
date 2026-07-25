"""Mirrored tests for :class:`CircuitBreakerRegistry` scoping (PIR-493 / S1)."""

from __future__ import annotations

import pytest

from pirn_agents.resilience.circuit_breaker_config import CircuitBreakerConfig
from pirn_agents.resilience.circuit_breaker_registry import CircuitBreakerRegistry
from pirn_agents.resilience.circuit_state import CircuitState


class TestConstruction:
    def test_rejects_non_config(self) -> None:
        with pytest.raises(TypeError, match="CircuitBreakerConfig"):
            CircuitBreakerRegistry(object())  # type: ignore[arg-type]


class TestScoping:
    def test_same_key_returns_same_breaker(self) -> None:
        registry = CircuitBreakerRegistry(CircuitBreakerConfig())
        assert registry.get("a") is registry.get("a")

    def test_distinct_keys_get_distinct_breakers(self) -> None:
        registry = CircuitBreakerRegistry(CircuitBreakerConfig())
        assert registry.get("a") is not registry.get("b")
        assert set(registry.endpoints()) == {"a", "b"}

    async def test_tripping_one_endpoint_leaves_others_closed(self) -> None:
        registry = CircuitBreakerRegistry(CircuitBreakerConfig(failure_threshold=1))
        await registry.get("dead").record_failure()
        assert registry.get("dead").state is CircuitState.OPEN
        assert registry.get("healthy").state is CircuitState.CLOSED

    def test_breaker_carries_endpoint_identity(self) -> None:
        registry = CircuitBreakerRegistry(CircuitBreakerConfig())
        assert registry.get("ep-x").endpoint == "ep-x"
