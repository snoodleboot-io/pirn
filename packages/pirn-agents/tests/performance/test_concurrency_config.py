"""Unit tests for :class:`ConcurrencyConfig` defaults and validation.

ADR agents-speaks-core, WS4b/PIR-866: ``ConcurrencyConfig`` is now a
:class:`~pirn.core.concurrency.concurrency_limits.ConcurrencyLimits`
subclass and a one-cycle deprecation shim; see
``TestDeprecationAndCoreSeam`` for the parts of this file that pin the
migration itself.
"""

from __future__ import annotations

import warnings

import pytest
from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits

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


class TestDeprecationAndCoreSeam:
    def test_warns_on_construction(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ConcurrencyConfig()
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    def test_is_a_concurrency_limits(self) -> None:
        config = ConcurrencyConfig(max_concurrency=5)
        assert isinstance(config, ConcurrencyLimits)

    def test_to_concurrency_limits_bare(self) -> None:
        config = ConcurrencyConfig(max_concurrency=5)
        limits = config.to_concurrency_limits()
        assert limits == ConcurrencyLimits(max_in_flight=5)

    def test_to_concurrency_limits_grouped(self) -> None:
        config = ConcurrencyConfig(max_concurrency=5)
        limits = config.to_concurrency_limits(group="openai")
        assert limits == ConcurrencyLimits(groups={"openai": 5})
