"""Unit tests for :class:`IFFTReconstructor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.ifft_reconstructor import IFFTReconstructor
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry


@knot
async def emit_spectrum_frame() -> SpectrumFrame:
    """Upstream knot emitting a deterministic SpectrumFrame."""
    return SpectrumFrame(signal_id="spec", frequency_bins=257, frequency_resolution_hz=1.953)


class TestConstruction:
    def test_accepts_spectrum_knot(self) -> None:
        with Tapestry():
            sp = emit_spectrum_frame(_config=KnotConfig(id="sp"))
            IFFTReconstructor(spectrum=sp, _config=KnotConfig(id="ifft"))


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sp = emit_spectrum_frame(_config=KnotConfig(id="sp"))
            IFFTReconstructor(spectrum=sp, _config=KnotConfig(id="ifft"))
        result = await t.run(RunRequest())
        out = result.outputs["ifft"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "spec:ifft"
        assert out.samples_per_channel == (257 - 1) * 2
