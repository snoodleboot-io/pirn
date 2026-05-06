"""Unit tests for :class:`WaveletDenoiser`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.wavelets.wavelet_denoiser import WaveletDenoiser
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_bare_knot(self) -> WaveletDenoiser:
        with Tapestry():
            k = WaveletDenoiser.__new__(WaveletDenoiser)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        return k

    async def test_rejects_empty_wavelet(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, wavelet="", level=3, threshold_mode="soft")  # type: ignore[arg-type]

    async def test_rejects_non_positive_level(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, wavelet="db4", level=0, threshold_mode="soft")  # type: ignore[arg-type]

    async def test_rejects_invalid_threshold_mode(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, wavelet="db4", level=3, threshold_mode="garrote")  # type: ignore[arg-type]


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
