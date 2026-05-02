"""Unit tests for :class:`WaveletFrame`."""

from __future__ import annotations

from pirn.domains.signal.types.wavelet_frame import WaveletFrame


class TestRoundtrip:
    def test_construct_with_defaults(self) -> None:
        frame = WaveletFrame()
        assert frame.signal_id == ""
        assert frame.wavelet_name == ""
        assert frame.scale_count == 0

    def test_construct_with_full_kwargs(self) -> None:
        frame = WaveletFrame(
            signal_id="sig-1",
            wavelet_name="db4",
            scale_count=8,
        )
        assert frame.signal_id == "sig-1"
        assert frame.wavelet_name == "db4"
        assert frame.scale_count == 8

    def test_audit_dict_returns_json_primitives(self) -> None:
        frame = WaveletFrame(
            signal_id="sig-2",
            wavelet_name="haar",
            scale_count=4,
        )
        d = frame._pirn_audit_dict()
        assert d == {
            "signal_id": "sig-2",
            "wavelet_name": "haar",
            "scale_count": 4,
        }

    def test_frozen_disallows_mutation(self) -> None:
        frame = WaveletFrame(signal_id="x")
        try:
            frame.signal_id = "y"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("WaveletFrame should be frozen")
