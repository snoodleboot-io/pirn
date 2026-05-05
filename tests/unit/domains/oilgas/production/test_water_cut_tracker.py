"""Unit tests for :class:`WaterCutTracker`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.water_cut_tracker import WaterCutTracker
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class _OilSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        return ScadaTimeSeries(sensor_id="oil", sample_interval_sec=60.0)


class _WaterSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        return ScadaTimeSeries(sensor_id="water", sample_interval_sec=60.0)


class TestConstruction(unittest.TestCase):
    def test_requires_oil_and_water(self) -> None:
        with self.assertRaises(TypeError):
            WaterCutTracker(_config=KnotConfig(id="wc"))  # type: ignore[call-arg]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_water_cut_series(self) -> None:
        with Tapestry() as t:
            o = _OilSource(_config=KnotConfig(id="o"))
            w = _WaterSource(_config=KnotConfig(id="w"))
            WaterCutTracker(
                oil_rate=o, water_rate=w, _config=KnotConfig(id="wc")
            )
        result = await t.run(RunRequest())
        out = result.outputs["wc"]
        assert isinstance(out, ScadaTimeSeries)
        assert out.sensor_id == "watercut:oil:water"
