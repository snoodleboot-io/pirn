"""Unit tests for :class:`SpectrumFrame`."""

from __future__ import annotations
import unittest

from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


class TestRoundtrip(unittest.TestCase):
    def test_construct_with_defaults(self) -> None:
        frame = SpectrumFrame()
        assert frame.signal_id == ""
        assert frame.frequency_bins == 0
        assert frame.frequency_resolution_hz == 0.0

    def test_construct_with_full_kwargs(self) -> None:
        frame = SpectrumFrame(
            signal_id="sig-1",
            frequency_bins=512,
            frequency_resolution_hz=10.0,
        )
        assert frame.signal_id == "sig-1"
        assert frame.frequency_bins == 512
        assert frame.frequency_resolution_hz == 10.0

    def test_audit_dict_returns_json_primitives(self) -> None:
        frame = SpectrumFrame(
            signal_id="sig-2",
            frequency_bins=128,
            frequency_resolution_hz=2.5,
        )
        d = frame._pirn_audit_dict()
        assert d == {
            "signal_id": "sig-2",
            "frequency_bins": 128,
            "frequency_resolution_hz": 2.5,
        }

    def test_frozen_disallows_mutation(self) -> None:
        frame = SpectrumFrame(signal_id="x")
        try:
            frame.signal_id = "y"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("SpectrumFrame should be frozen")
