"""Unit tests for :class:`ButterworthFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.butterworth_filter import ButterworthFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_order(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "positive integer"):
                ButterworthFilter(
                    signal=sig,
                    order=0,
                    cutoff_hz=10.0,
                    _config=KnotConfig(id="bw"),
                )

    def test_rejects_invalid_band_type(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "band_type"):
                ButterworthFilter(
                    signal=sig,
                    order=4,
                    cutoff_hz=10.0,
                    band_type="invalid",
                    _config=KnotConfig(id="bw"),
                )

    def test_rejects_scalar_cutoff_for_bandpass(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "bandpass/bandstop"):
                ButterworthFilter(
                    signal=sig,
                    order=4,
                    cutoff_hz=10.0,
                    band_type="bandpass",
                    _config=KnotConfig(id="bw"),
                )

    def test_rejects_invalid_band_bounds(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "0 < low < high"):
                ButterworthFilter(
                    signal=sig,
                    order=4,
                    cutoff_hz=(20.0, 10.0),
                    band_type="bandpass",
                    _config=KnotConfig(id="bw"),
                )

    def test_rejects_non_positive_lowpass_cutoff(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "positive scalar"):
                ButterworthFilter(
                    signal=sig,
                    order=4,
                    cutoff_hz=0,
                    _config=KnotConfig(id="bw"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame_with_band_marker(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ButterworthFilter(
                signal=sig,
                order=4,
                cutoff_hz=100.0,
                band_type="lowpass",
                _config=KnotConfig(id="bw"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["bw"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:butter-lowpass"
        assert out.sample_rate_hz == 1000.0
