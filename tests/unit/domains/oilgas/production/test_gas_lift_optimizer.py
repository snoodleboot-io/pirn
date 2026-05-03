"""Unit tests for :class:`GasLiftOptimizer`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.gas_lift_optimizer import GasLiftOptimizer
from pirn.tapestry import Tapestry


class _WellDataSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {
            "current_injection_mmscfd": 0.5,
            "performance_curve": [
                {"injection_mmscfd": 0.0, "oil_bopd": 200.0},
                {"injection_mmscfd": 0.5, "oil_bopd": 400.0},
                {"injection_mmscfd": 1.0, "oil_bopd": 550.0},
                {"injection_mmscfd": 1.5, "oil_bopd": 580.0},
                {"injection_mmscfd": 2.0, "oil_bopd": 560.0},
            ],
        }


class TestConstruction:
    def test_rejects_non_positive_cost(self) -> None:
        with pytest.raises(ValueError, match="injection_gas_cost_per_mscf"):
            with Tapestry():
                src = _WellDataSource(_config=KnotConfig(id="src"))
                GasLiftOptimizer(
                    well_data=src,
                    injection_gas_cost_per_mscf=0.0,
                    max_injection_rate_mmscfd=2.0,
                    _config=KnotConfig(id="gl"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_optimal_injection(self) -> None:
        with Tapestry() as t:
            src = _WellDataSource(_config=KnotConfig(id="src"))
            GasLiftOptimizer(
                well_data=src,
                injection_gas_cost_per_mscf=2.5,
                max_injection_rate_mmscfd=2.0,
                _config=KnotConfig(id="gl"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["gl"]
        assert "optimal_injection_mmscfd" in out
        assert "projected_oil_bopd" in out
        assert "incremental_bopd" in out
        assert out["projected_oil_bopd"] > 0.0
