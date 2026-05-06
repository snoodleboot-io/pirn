"""Unit tests for :class:`MFCCExtractor`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.audio.mfcc_extractor import MFCCExtractor
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestMFCCExtractor(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> MFCCExtractor:
        return MFCCExtractor(
            signal=_up(),
            n_mfcc=13,
            n_fft=512,
            hop_length=256,
            _config=KnotConfig(id="mfcc"),
        )

    async def test_rejects_non_positive_n_mfcc(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="n_mfcc"):
            await knot.process(_SIGNAL, n_mfcc=0, n_fft=512, hop_length=256)

    async def test_rejects_non_positive_n_fft(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="n_fft"):
            await knot.process(_SIGNAL, n_mfcc=13, n_fft=0, hop_length=256)

    async def test_rejects_hop_exceeding_n_fft(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="hop_length"):
            await knot.process(_SIGNAL, n_mfcc=13, n_fft=256, hop_length=512)

    async def test_emits_spectrum_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, n_mfcc=13, n_fft=512, hop_length=256)
        assert isinstance(out, SpectrumFrame)
        assert out.frequency_bins == 13
