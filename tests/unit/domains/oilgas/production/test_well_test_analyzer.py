"""Unit tests for :class:`WellTestAnalyzer`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.well_test_analyzer import WellTestAnalyzer
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class _Source(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        return ScadaTimeSeries(sensor_id="p")


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            with Tapestry():
                src = _Source(_config=KnotConfig(id="src"))
                WellTestAnalyzer(
                    pressure_series=src,
                    method="bogus",
                    _config=KnotConfig(id="wt"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_perm_skin(self) -> None:
        with Tapestry() as t:
            src = _Source(_config=KnotConfig(id="src"))
            WellTestAnalyzer(
                pressure_series=src,
                method="horner",
                _config=KnotConfig(id="wt"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["wt"]
        assert "permeability_md" in out
        assert "skin" in out
