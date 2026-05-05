"""Unit tests for :class:`CathodicProtectionAnalyzer`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.integrity.cathodic_protection_analyzer import (
    CathodicProtectionAnalyzer,
)
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class _Source(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        return ScadaTimeSeries(sensor_id="potential")


class TestConstruction(unittest.TestCase):
    def test_rejects_non_numeric_threshold(self) -> None:
        with self.assertRaisesRegex(TypeError, "protection_threshold_mv"):
            with Tapestry():
                src = _Source(_config=KnotConfig(id="src"))
                CathodicProtectionAnalyzer(
                    potential_series=src,
                    protection_threshold_mv="x",  # type: ignore[arg-type]
                    _config=KnotConfig(id="cp"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_coverage(self) -> None:
        with Tapestry() as t:
            src = _Source(_config=KnotConfig(id="src"))
            CathodicProtectionAnalyzer(
                potential_series=src,
                protection_threshold_mv=-850.0,
                _config=KnotConfig(id="cp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["cp"]
        assert "coverage_fraction" in out
        assert out["threshold_mv"] == -850.0
