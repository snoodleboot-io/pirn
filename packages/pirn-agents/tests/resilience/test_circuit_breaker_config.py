"""Mirrored tests for :class:`CircuitBreakerConfig` validation (PIR-493 / S1)."""

from __future__ import annotations

import pytest

from pirn_agents.resilience.circuit_breaker_config import CircuitBreakerConfig


class TestDefaults:
    def test_sane_defaults(self) -> None:
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.cooldown_seconds == 30.0
        assert config.success_threshold == 1

    def test_audit_dict_is_primitive(self) -> None:
        assert CircuitBreakerConfig()._pirn_audit_dict() == {
            "failure_threshold": 5,
            "cooldown_seconds": 30.0,
            "success_threshold": 1,
        }


class TestValidation:
    @pytest.mark.parametrize("bad", [0, -1, True, 1.5])
    def test_rejects_bad_failure_threshold(self, bad: object) -> None:
        with pytest.raises(ValueError, match="failure_threshold"):
            CircuitBreakerConfig(failure_threshold=bad)  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad", [0, -1, True, 2.0])
    def test_rejects_bad_success_threshold(self, bad: object) -> None:
        with pytest.raises(ValueError, match="success_threshold"):
            CircuitBreakerConfig(success_threshold=bad)  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad", [0, -1.0, True, "x"])
    def test_rejects_bad_cooldown(self, bad: object) -> None:
        with pytest.raises(ValueError, match="cooldown_seconds"):
            CircuitBreakerConfig(cooldown_seconds=bad)  # type: ignore[arg-type]
