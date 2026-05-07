"""Unit tests for :class:`DowntimeEventClassifier`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.production.downtime_event_classifier import (
    DowntimeEventClassifier,
)

_SERIES_WITH_GAP: list[dict[str, Any]] = [
    {"timestamp_iso": "2026-01-01T00:00:00Z", "rate_bopd": 100.0},
    {"timestamp_iso": "2026-01-02T00:00:00Z", "rate_bopd": 0.0},
    {"timestamp_iso": "2026-01-03T00:00:00Z", "rate_bopd": 0.0},
    {"timestamp_iso": "2026-01-04T00:00:00Z", "rate_bopd": 80.0},
]
_SERIES_NO_GAP: list[dict[str, Any]] = [
    {"timestamp_iso": "2026-01-01T00:00:00Z", "rate_bopd": 100.0},
    {"timestamp_iso": "2026-01-02T00:00:00Z", "rate_bopd": 90.0},
]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, gap_threshold_hours: float = 4.0) -> DowntimeEventClassifier:
        return DowntimeEventClassifier(
            production_series=None,  # type: ignore[arg-type]
            gap_threshold_hours=gap_threshold_hours,
            _config=KnotConfig(id="dec", validate_io=False),
        )

    async def test_rejects_zero_threshold(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "gap_threshold_hours"):
            await knot.process(production_series=_SERIES_WITH_GAP, gap_threshold_hours=0.0)

    async def test_rejects_non_numeric_threshold(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "gap_threshold_hours"):
            await knot.process(production_series=_SERIES_WITH_GAP, gap_threshold_hours="4")  # type: ignore[arg-type]

    async def test_detects_downtime_event(self) -> None:
        knot = self._make_knot(gap_threshold_hours=4.0)
        out = await knot.process(production_series=_SERIES_WITH_GAP, gap_threshold_hours=4.0)
        assert isinstance(out, list)
        assert len(out) == 1
        assert "start_iso" in out[0]
        assert "category" in out[0]

    async def test_returns_empty_list_for_no_gaps(self) -> None:
        knot = self._make_knot(gap_threshold_hours=4.0)
        out = await knot.process(production_series=_SERIES_NO_GAP, gap_threshold_hours=4.0)
        assert out == []

    async def test_raises_on_missing_timestamp_field(self) -> None:
        knot = self._make_knot()
        bad = [{"rate_bopd": 100.0}]
        with self.assertRaisesRegex(KeyError, "timestamp_iso"):
            await knot.process(production_series=bad, gap_threshold_hours=4.0)

    async def test_raises_on_missing_rate_field(self) -> None:
        knot = self._make_knot()
        bad = [{"timestamp_iso": "2026-01-01T00:00:00Z"}]
        with self.assertRaisesRegex(KeyError, "rate_bopd"):
            await knot.process(production_series=bad, gap_threshold_hours=4.0)

    async def test_custom_field_names(self) -> None:
        knot = self._make_knot()
        scada_series: list[dict[str, Any]] = [
            {"TS": "2026-01-01T00:00:00Z", "RATE": 100.0},
            {"TS": "2026-01-02T00:00:00Z", "RATE": 0.0},
            {"TS": "2026-01-03T00:00:00Z", "RATE": 80.0},
        ]
        out = await knot.process(
            production_series=scada_series,
            gap_threshold_hours=4.0,
            timestamp_field="TS",
            rate_field="RATE",
        )
        assert len(out) == 1
