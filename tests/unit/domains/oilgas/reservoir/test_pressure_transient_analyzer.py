"""Unit tests for :class:`PressureTransientAnalyzer`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.reservoir.pressure_transient_analyzer import (
    PressureTransientAnalyzer,
)
from pirn.tapestry import Tapestry


class _TestDataSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {
            "time_hours": [0.0, 1.0, 2.0, 4.0, 8.0],
            "pressure_psi": [3000.0, 3050.0, 3080.0, 3100.0, 3110.0],
            "flow_rate_bopd": 200.0,
        }


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_radius(self) -> None:
        with self.assertRaisesRegex(ValueError, "wellbore_radius_ft"):
            with Tapestry():
                src = _TestDataSource(_config=KnotConfig(id="src"))
                PressureTransientAnalyzer(
                    test_data=src,
                    wellbore_radius_ft=0.0,
                    formation_thickness_ft=30.0,
                    fluid_viscosity_cp=2.0,
                    _config=KnotConfig(id="pta"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_reservoir_params(self) -> None:
        with Tapestry() as t:
            src = _TestDataSource(_config=KnotConfig(id="src"))
            PressureTransientAnalyzer(
                test_data=src,
                wellbore_radius_ft=0.328,
                formation_thickness_ft=30.0,
                fluid_viscosity_cp=2.0,
                _config=KnotConfig(id="pta"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["pta"]
        assert "permeability_md" in out
        assert "skin_factor" in out
        assert "wellbore_storage" in out
        assert "pi_bopd_psi" in out

    async def test_records_error_on_empty_time_series(self) -> None:
        class _EmptySource(Knot):
            def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
                super().__init__(_config=_config, **kwargs)

            async def process(self, **_: Any) -> dict[str, Any]:
                return {"time_hours": [], "pressure_psi": [], "flow_rate_bopd": 100.0}

        with Tapestry() as t:
            src = _EmptySource(_config=KnotConfig(id="src"))
            PressureTransientAnalyzer(
                test_data=src,
                wellbore_radius_ft=0.328,
                formation_thickness_ft=30.0,
                fluid_viscosity_cp=2.0,
                _config=KnotConfig(id="pta"),
            )
        result = await t.run(RunRequest())
        assert any(e.exc_type == "ValueError" for e in result.exceptions)
