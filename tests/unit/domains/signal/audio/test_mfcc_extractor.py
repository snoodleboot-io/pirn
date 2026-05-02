"""Unit tests for :class:`MFCCExtractor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.audio.mfcc_extractor import MFCCExtractor
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_n_mfcc(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="n_mfcc"):
                MFCCExtractor(
                    signal=sig,
                    n_mfcc=0,
                    n_fft=512,
                    hop_length=128,
                    _config=KnotConfig(id="m"),
                )

    def test_rejects_non_positive_n_fft(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="n_fft"):
                MFCCExtractor(
                    signal=sig,
                    n_mfcc=13,
                    n_fft=0,
                    hop_length=128,
                    _config=KnotConfig(id="m"),
                )

    def test_rejects_hop_above_n_fft(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="not exceed"):
                MFCCExtractor(
                    signal=sig,
                    n_mfcc=13,
                    n_fft=128,
                    hop_length=512,
                    _config=KnotConfig(id="m"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_spectrum_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            MFCCExtractor(
                signal=sig,
                n_mfcc=13,
                n_fft=512,
                hop_length=128,
                _config=KnotConfig(id="m"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["m"]
        assert isinstance(out, SpectrumFrame)
        assert out.frequency_bins == 13
