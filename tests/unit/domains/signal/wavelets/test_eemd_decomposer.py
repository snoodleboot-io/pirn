"""Unit tests for :class:`EEMDDecomposer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.types.wavelet_frame import WaveletFrame
from pirn.domains.signal.wavelets.eemd_decomposer import EEMDDecomposer
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_bare_knot(self) -> EEMDDecomposer:
        with Tapestry():
            k = EEMDDecomposer.__new__(EEMDDecomposer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        return k

    async def test_rejects_non_positive_ensemble_size(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, ensemble_size=0, noise_amplitude=0.1, max_imf_count=4)  # type: ignore[arg-type]

    async def test_rejects_non_positive_noise_amplitude(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, ensemble_size=10, noise_amplitude=0, max_imf_count=4)  # type: ignore[arg-type]

    async def test_rejects_non_positive_max_imf_count(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, ensemble_size=10, noise_amplitude=0.1, max_imf_count=0)  # type: ignore[arg-type]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_wavelet_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            EEMDDecomposer(
                signal=sig,
                ensemble_size=10,
                noise_amplitude=0.1,
                max_imf_count=4,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, WaveletFrame)
        assert out.wavelet_name == "eemd"
        assert out.scale_count == 4
