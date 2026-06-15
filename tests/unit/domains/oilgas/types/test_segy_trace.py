"""Unit tests for :class:`SegyTrace`."""

from __future__ import annotations

import unittest

from pirn_oilgas.types.segy_trace import SegyTrace


class TestConstruction(unittest.TestCase):
    def test_default_values(self) -> None:
        trace = SegyTrace()
        assert trace.trace_id == ""
        assert trace.sample_count == 0
        assert trace.sample_interval_ms == 0.0

    def test_full_values(self) -> None:
        trace = SegyTrace(
            trace_id="t-1",
            sample_count=1000,
            sample_interval_ms=4.0,
        )
        assert trace.trace_id == "t-1"
        assert trace.sample_count == 1000
        assert trace.sample_interval_ms == 4.0


class TestAuditDict(unittest.TestCase):
    def test_audit_dict_round_trip(self) -> None:
        trace = SegyTrace(trace_id="t-1", sample_count=10, sample_interval_ms=2.0)
        assert trace._pirn_audit_dict() == {
            "trace_id": "t-1",
            "sample_count": 10,
            "sample_interval_ms": 2.0,
        }


class TestFrozen(unittest.TestCase):
    def test_frozen_disallows_mutation(self) -> None:
        trace = SegyTrace(trace_id="t-1")
        try:
            trace.trace_id = "x"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("SegyTrace must be frozen")
