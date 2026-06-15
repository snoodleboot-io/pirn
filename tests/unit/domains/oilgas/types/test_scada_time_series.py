"""Unit tests for :class:`ScadaTimeSeries`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn_oilgas.types.scada_time_series import ScadaTimeSeries


class TestConstruction(unittest.TestCase):
    def test_default_values(self) -> None:
        series = ScadaTimeSeries()
        assert series.sensor_id == ""
        assert series.sample_count == 0
        assert series.sample_interval_sec == 0.0
        assert isinstance(series.fetched_at, datetime)

    def test_full_values(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
        series = ScadaTimeSeries(
            sensor_id="s",
            sample_count=10,
            sample_interval_sec=60.0,
            fetched_at=when,
        )
        assert series.sensor_id == "s"
        assert series.sample_count == 10
        assert series.sample_interval_sec == 60.0
        assert series.fetched_at == when


class TestAuditDict(unittest.TestCase):
    def test_audit_dict_keys(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
        series = ScadaTimeSeries(
            sensor_id="s",
            sample_count=2,
            sample_interval_sec=1.0,
            fetched_at=when,
        )
        d = series._pirn_audit_dict()
        assert d == {
            "sensor_id": "s",
            "sample_count": 2,
            "sample_interval_sec": 1.0,
            "fetched_at": when.isoformat(),
        }


class TestFrozen(unittest.TestCase):
    def test_frozen_disallows_mutation(self) -> None:
        series = ScadaTimeSeries(sensor_id="s")
        try:
            series.sensor_id = "x"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("ScadaTimeSeries must be frozen")
