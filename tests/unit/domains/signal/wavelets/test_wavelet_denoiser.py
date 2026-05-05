"""Unit tests for :class:`WaveletDenoiser`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.wavelets.wavelet_denoiser import WaveletDenoiser
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_wavelet(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                WaveletDenoiser(
                    signal=sig,
                    wavelet="",
                    level=3,
                    threshold_mode="soft",
                    _config=KnotConfig(id="d"),
                )

    def test_rejects_non_positive_level(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "level"):
                WaveletDenoiser(
                    signal=sig,
                    wavelet="db4",
                    level=0,
                    threshold_mode="soft",
                    _config=KnotConfig(id="d"),
                )

    def test_rejects_invalid_threshold_mode(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "threshold_mode"):
                WaveletDenoiser(
                    signal=sig,
                    wavelet="db4",
                    level=3,
                    threshold_mode="garrote",
                    _config=KnotConfig(id="d"),
                )

    def test_accepts_hard_threshold(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            WaveletDenoiser(
                signal=sig,
                wavelet="db4",
                level=3,
                threshold_mode="hard",
                _config=KnotConfig(id="d"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame_with_mode_marker(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            WaveletDenoiser(
                signal=sig,
                wavelet="db4",
                level=3,
                threshold_mode="soft",
                _config=KnotConfig(id="d"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["d"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:denoised-soft"
        assert out.sample_rate_hz == 1000.0
