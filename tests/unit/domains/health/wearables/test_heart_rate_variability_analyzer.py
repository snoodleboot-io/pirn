"""Unit tests for :class:`HeartRateVariabilityAnalyzer`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.wearables.heart_rate_variability_analyzer import (
    HeartRateVariabilityAnalyzer,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence(self) -> None:
        inst = object.__new__(HeartRateVariabilityAnalyzer)
        with self.assertRaisesRegex(TypeError, "rr_intervals_ms"):
            await HeartRateVariabilityAnalyzer.process(
                inst,
                rr_intervals_ms=42,  # type: ignore[arg-type]
            )

    async def test_rejects_non_numeric(self) -> None:
        inst = object.__new__(HeartRateVariabilityAnalyzer)
        with self.assertRaisesRegex(TypeError, "numeric"):
            await HeartRateVariabilityAnalyzer.process(
                inst,
                rr_intervals_ms=["x"],  # type: ignore[list-item]
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_metric_mapping(self) -> None:
        with Tapestry() as t:
            HeartRateVariabilityAnalyzer(
                rr_intervals_ms=[800.0, 820.0, 810.0],
                _config=KnotConfig(id="h"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["h"]
        assert isinstance(out, Mapping)
        assert "sdnn" in out
        assert "rmssd" in out
