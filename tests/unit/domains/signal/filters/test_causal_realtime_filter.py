"""Unit tests for :class:`CausalRealtimeFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.filters.causal_realtime_filter import CausalRealtimeFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_filter_type(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "filter_type"):
                CausalRealtimeFilter(
                    signal=sig,
                    filter_type="invalid",
                    cutoff_hz=100.0,
                    order=4,
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_non_positive_order(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "positive integer"):
                CausalRealtimeFilter(
                    signal=sig,
                    filter_type="lowpass",
                    cutoff_hz=100.0,
                    order=0,
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_scalar_cutoff_for_bandpass(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "bandpass/bandstop"):
                CausalRealtimeFilter(
                    signal=sig,
                    filter_type="bandpass",
                    cutoff_hz=100.0,
                    order=4,
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_non_positive_lowpass_cutoff(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "positive scalar"):
                CausalRealtimeFilter(
                    signal=sig,
                    filter_type="lowpass",
                    cutoff_hz=0.0,
                    order=4,
                    _config=KnotConfig(id="f"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame_with_type_marker(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            CausalRealtimeFilter(
                signal=sig,
                filter_type="highpass",
                cutoff_hz=50.0,
                order=2,
                _config=KnotConfig(id="f"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["f"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:causal-highpass"
        assert out.sample_rate_hz == 1000.0
