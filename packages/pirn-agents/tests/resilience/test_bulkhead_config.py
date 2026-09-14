"""Mirrored tests for :class:`BulkheadConfig` (PIR-503 / S4)."""

from __future__ import annotations

import warnings

import pytest
from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits

from pirn_agents.performance.concurrency_config import ConcurrencyConfig
from pirn_agents.resilience.bulkhead_config import BulkheadConfig


class TestDefaults:
    def test_default_pool_applies_without_override(self) -> None:
        config = BulkheadConfig(default=ConcurrencyConfig(max_concurrency=4))
        assert config.for_backend("unknown").max_concurrency == 4

    def test_override_wins_for_named_backend(self) -> None:
        config = BulkheadConfig(
            default=ConcurrencyConfig(max_concurrency=4),
            overrides={"x": ConcurrencyConfig(max_concurrency=1)},
        )
        assert config.for_backend("x").max_concurrency == 1
        assert config.for_backend("y").max_concurrency == 4


class TestValidation:
    def test_rejects_bad_default(self) -> None:
        with pytest.raises(TypeError, match="default must be a ConcurrencyConfig"):
            BulkheadConfig(default=object())  # type: ignore[arg-type]

    def test_rejects_bad_override_value(self) -> None:
        with pytest.raises(TypeError, match="overrides"):
            BulkheadConfig(overrides={"x": object()})  # type: ignore[dict-item]

    def test_audit_dict_projects_pools(self) -> None:
        config = BulkheadConfig(
            default=ConcurrencyConfig(max_concurrency=2),
            overrides={"x": ConcurrencyConfig(max_concurrency=1)},
        )
        audit = config._pirn_audit_dict()
        assert audit["default"]["max_concurrency"] == 2
        assert audit["overrides"]["x"]["max_concurrency"] == 1


class TestDeprecationAndCoreSeam:
    def test_warns_on_construction(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            BulkheadConfig()
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    def test_to_concurrency_limits_projects_overrides_only(self) -> None:
        config = BulkheadConfig(
            default=ConcurrencyConfig(max_concurrency=4),
            overrides={"x": ConcurrencyConfig(max_concurrency=1)},
        )
        limits = config.to_concurrency_limits()
        assert limits == ConcurrencyLimits(groups={"x": 1})
        assert limits.group_limit("unnamed-default-only") is None

    def test_to_concurrency_limits_rejects_an_invalid_backend_name(self) -> None:
        config = BulkheadConfig(overrides={"has a space": ConcurrencyConfig()})
        with pytest.raises(ValueError, match="invalid characters"):
            config.to_concurrency_limits()
