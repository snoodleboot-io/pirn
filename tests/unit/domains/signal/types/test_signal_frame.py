"""Unit tests for :class:`SignalFrame`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.domains.signal.types.signal_frame import SignalFrame


class TestRoundtrip(unittest.TestCase):
    def test_construct_with_defaults(self) -> None:
        frame = SignalFrame()
        assert frame.signal_id == ""
        assert frame.channel_count == 0
        assert frame.sample_rate_hz == 0.0
        assert frame.samples_per_channel == 0
        assert isinstance(frame.fetched_at, datetime)

    def test_construct_with_full_kwargs(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
        frame = SignalFrame(
            signal_id="sig-1",
            channel_count=2,
            sample_rate_hz=48_000.0,
            samples_per_channel=1024,
            fetched_at=when,
        )
        assert frame.signal_id == "sig-1"
        assert frame.channel_count == 2
        assert frame.sample_rate_hz == 48_000.0
        assert frame.samples_per_channel == 1024
        assert frame.fetched_at == when

    def test_audit_dict_returns_json_primitives(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=UTC)
        frame = SignalFrame(
            signal_id="sig-2",
            channel_count=1,
            sample_rate_hz=1000.0,
            samples_per_channel=512,
            fetched_at=when,
        )
        d = frame._pirn_audit_dict()
        assert d == {
            "signal_id": "sig-2",
            "channel_count": 1,
            "sample_rate_hz": 1000.0,
            "samples_per_channel": 512,
            "fetched_at": when.isoformat(),
        }

    def test_frozen_disallows_mutation(self) -> None:
        frame = SignalFrame(signal_id="x")
        try:
            frame.signal_id = "y"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("SignalFrame should be frozen")
