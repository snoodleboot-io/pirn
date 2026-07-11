"""Unit tests for :class:`ConcurrencyConfig` defaults and validation."""

from __future__ import annotations

import pytest

from pirn_agents.performance.concurrency_config import ConcurrencyConfig


class TestConcurrencyConfig:
    def test_sensible_defaults(self) -> None:
        config = ConcurrencyConfig()
        assert config.max_concurrency == 8
        assert config.max_queue_depth is None
        assert config.acquire_timeout is None

    def test_overridable(self) -> None:
        config = ConcurrencyConfig(max_concurrency=2, max_queue_depth=4, acquire_timeout=0.5)
        assert config.max_concurrency == 2
        assert config.max_queue_depth == 4
        assert config.acquire_timeout == 0.5

    @pytest.mark.parametrize("bad", [0, -1, True])
    def test_bad_max_concurrency_rejected(self, bad: int) -> None:
        with pytest.raises(ValueError, match="max_concurrency"):
            ConcurrencyConfig(max_concurrency=bad)

    def test_negative_queue_depth_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_queue_depth"):
            ConcurrencyConfig(max_queue_depth=-1)

    def test_non_positive_timeout_rejected(self) -> None:
        with pytest.raises(ValueError, match="acquire_timeout"):
            ConcurrencyConfig(acquire_timeout=0)

    def test_audit_dict(self) -> None:
        config = ConcurrencyConfig(max_concurrency=3)
        assert config._pirn_audit_dict() == {
            "max_concurrency": 3,
            "max_queue_depth": None,
            "acquire_timeout": None,
        }

    def test_frozen_and_equal(self) -> None:
        assert ConcurrencyConfig(max_concurrency=4) == ConcurrencyConfig(max_concurrency=4)
