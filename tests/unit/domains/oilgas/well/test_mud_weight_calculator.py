"""Unit tests for :class:`MudWeightCalculator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.well.mud_weight_calculator import MudWeightCalculator
from pirn.domains.oilgas.well.well_completion_ingester import WellCompletionIngester
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_negative_pore_pressure(self) -> None:
        with self.assertRaisesRegex(ValueError, "pore_pressure_ppg"):
            with Tapestry():
                drill = WellCompletionIngester(
                    well_id="W", record_path="/x", _config=KnotConfig(id="wc")
                )
                MudWeightCalculator(
                    drilling=drill,
                    pore_pressure_ppg=-1.0,
                    fracture_pressure_ppg=15.0,
                    _config=KnotConfig(id="mw"),
                )

    def test_rejects_inverted_pressures(self) -> None:
        with self.assertRaisesRegex(ValueError, "fracture_pressure_ppg"):
            with Tapestry():
                drill = WellCompletionIngester(
                    well_id="W", record_path="/x", _config=KnotConfig(id="wc")
                )
                MudWeightCalculator(
                    drilling=drill,
                    pore_pressure_ppg=15.0,
                    fracture_pressure_ppg=10.0,
                    _config=KnotConfig(id="mw"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_window(self) -> None:
        with Tapestry() as t:
            drill = WellCompletionIngester(
                well_id="W", record_path="/x", _config=KnotConfig(id="wc")
            )
            MudWeightCalculator(
                drilling=drill,
                pore_pressure_ppg=10.0,
                fracture_pressure_ppg=15.0,
                safety_margin_ppg=0.5,
                _config=KnotConfig(id="mw"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["mw"]
        assert out["min_ppg"] == 10.5
        assert out["max_ppg"] == 14.5
