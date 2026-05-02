"""Unit tests for :class:`EnergyEfficiencyKpiCalculator`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.integrity.energy_efficiency_kpi_calculator import (
    EnergyEfficiencyKpiCalculator,
)
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class _Source(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        return ScadaTimeSeries(sensor_id="s")


class TestConstruction:
    def test_requires_both_inputs(self) -> None:
        with pytest.raises(TypeError):
            EnergyEfficiencyKpiCalculator(_config=KnotConfig(id="e"))  # type: ignore[call-arg]


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_kpi_dict(self) -> None:
        with Tapestry() as t:
            e = _Source(_config=KnotConfig(id="e"))
            p = _Source(_config=KnotConfig(id="p"))
            EnergyEfficiencyKpiCalculator(
                energy_consumption=e,
                production=p,
                _config=KnotConfig(id="ek"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ek"]
        assert "kwh_per_boe" in out
        assert "energy_intensity_index" in out
