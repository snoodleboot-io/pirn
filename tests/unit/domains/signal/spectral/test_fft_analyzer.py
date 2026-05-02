"""Unit tests for :class:`FFTAnalyzer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.fft_analyzer import FFTAnalyzer
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_requires_n_fft(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(TypeError):
                FFTAnalyzer(signal=sig, _config=KnotConfig(id="fft"))  # type: ignore[call-arg]

    def test_rejects_non_integer_n_fft(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive integer"):
                FFTAnalyzer(
                    signal=sig,
                    n_fft=2.5,  # type: ignore[arg-type]
                    _config=KnotConfig(id="fft"),
                )

    def test_rejects_zero_n_fft(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive integer"):
                FFTAnalyzer(signal=sig, n_fft=0, _config=KnotConfig(id="fft"))

    def test_rejects_non_power_of_two(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="power of two"):
                FFTAnalyzer(signal=sig, n_fft=3, _config=KnotConfig(id="fft"))


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_spectrum_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            FFTAnalyzer(signal=sig, n_fft=512, _config=KnotConfig(id="fft"))
        result = await t.run(RunRequest())
        out = result.outputs["fft"]
        assert isinstance(out, SpectrumFrame)
        assert out.signal_id == "test"
        assert out.frequency_bins == 257
        assert out.frequency_resolution_hz == pytest.approx(1000.0 / 512)
