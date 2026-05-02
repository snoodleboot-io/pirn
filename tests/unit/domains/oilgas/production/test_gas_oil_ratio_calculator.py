"""Unit tests for :class:`GasOilRatioCalculator`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.gas_oil_ratio_calculator import (
    GasOilRatioCalculator,
)
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class _OilSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        return ScadaTimeSeries(sensor_id="oil", sample_interval_sec=60.0)


class _GasSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        return ScadaTimeSeries(sensor_id="gas", sample_interval_sec=60.0)


class TestConstruction:
    def test_requires_oil_and_gas(self) -> None:
        with pytest.raises(TypeError):
            GasOilRatioCalculator(_config=KnotConfig(id="g"))  # type: ignore[call-arg]


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_gor_series(self) -> None:
        with Tapestry() as t:
            o = _OilSource(_config=KnotConfig(id="o"))
            g = _GasSource(_config=KnotConfig(id="g"))
            GasOilRatioCalculator(
                oil_rate=o, gas_rate=g, _config=KnotConfig(id="gor")
            )
        result = await t.run(RunRequest())
        out = result.outputs["gor"]
        assert isinstance(out, ScadaTimeSeries)
        assert out.sensor_id == "gor:oil:gas"
