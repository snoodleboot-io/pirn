"""Unit tests for :class:`TypeCurveFitter`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.reservoir.type_curve_fitter import TypeCurveFitter
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class _RateSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        return ScadaTimeSeries(sensor_id="s")


class TestConstruction(unittest.TestCase):
    def test_requires_rate_series(self) -> None:
        with self.assertRaisesRegex(TypeError, "rate_series"):
            TypeCurveFitter(_config=KnotConfig(id="tc"))  # type: ignore[call-arg]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_eur(self) -> None:
        with Tapestry() as t:
            src = _RateSource(_config=KnotConfig(id="src"))
            TypeCurveFitter(rate_series=src, _config=KnotConfig(id="tc"))
        result = await t.run(RunRequest())
        out = result.outputs["tc"]
        assert "qi" in out
        assert "eur_stb" in out
