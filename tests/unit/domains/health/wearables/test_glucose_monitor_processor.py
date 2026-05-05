"""Unit tests for :class:`GlucoseMonitorProcessor`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.wearables.glucose_monitor_processor import (
    GlucoseMonitorProcessor,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "readings"):
            GlucoseMonitorProcessor(
                readings=42,  # type: ignore[arg-type]
                target_low_mg_dl=70.0,
                target_high_mg_dl=180.0,
                _config=KnotConfig(id="g"),
            )

    def test_rejects_non_mapping_reading(self) -> None:
        with self.assertRaisesRegex(TypeError, "reading"):
            GlucoseMonitorProcessor(
                readings=["x"],  # type: ignore[list-item]
                target_low_mg_dl=70.0,
                target_high_mg_dl=180.0,
                _config=KnotConfig(id="g"),
            )

    def test_rejects_low_ge_high(self) -> None:
        with self.assertRaisesRegex(ValueError, "<"):
            GlucoseMonitorProcessor(
                readings=[],
                target_low_mg_dl=180.0,
                target_high_mg_dl=70.0,
                _config=KnotConfig(id="g"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_metric_mapping(self) -> None:
        with Tapestry() as t:
            GlucoseMonitorProcessor(
                readings=[{"value": 100.0}],
                target_low_mg_dl=70.0,
                target_high_mg_dl=180.0,
                _config=KnotConfig(id="g"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["g"]
        assert isinstance(out, Mapping)
        assert "mean_glucose" in out
