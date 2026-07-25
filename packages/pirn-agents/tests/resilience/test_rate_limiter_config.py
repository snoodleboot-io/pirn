"""Mirrored tests for :class:`RateLimiterConfig` validation (PIR-499 / S3)."""

from __future__ import annotations

import pytest

from pirn_agents.resilience.rate_limiter_config import RateLimiterConfig


class TestValidation:
    def test_valid_config_audit_dict(self) -> None:
        config = RateLimiterConfig(refill_rate=2.0, capacity=10.0)
        assert config._pirn_audit_dict() == {"refill_rate": 2.0, "capacity": 10.0}

    @pytest.mark.parametrize("bad", [0, -1.0, True])
    def test_rejects_bad_refill_rate(self, bad: object) -> None:
        with pytest.raises(ValueError, match="refill_rate"):
            RateLimiterConfig(refill_rate=bad, capacity=1.0)  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad", [0, -5.0, True])
    def test_rejects_bad_capacity(self, bad: object) -> None:
        with pytest.raises(ValueError, match="capacity"):
            RateLimiterConfig(refill_rate=1.0, capacity=bad)  # type: ignore[arg-type]
