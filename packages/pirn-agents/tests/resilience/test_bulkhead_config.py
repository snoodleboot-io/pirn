"""Mirrored tests for :class:`BulkheadConfig` (PIR-503 / S4)."""

from __future__ import annotations

import pytest

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
