"""Unit tests for :class:`MelSpectrogramExtractor`."""

from __future__ import annotations

import unittest

try:
    import librosa  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("librosa not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.audio.mel_spectrogram_extractor import MelSpectrogramExtractor
from pirn_signal.types.signal_payload import SignalPayload

from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestMelSpectrogramExtractor(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> MelSpectrogramExtractor:
        return MelSpectrogramExtractor(
            signal=_up(),
            n_mels=128,
            n_fft=512,
            hop_length=256,
            _config=KnotConfig(id="mel"),
        )

    async def test_rejects_non_positive_n_mels(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="n_mels"):
            await knot.process(_SIGNAL, n_mels=0, n_fft=512, hop_length=256)

    async def test_rejects_non_positive_n_fft(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="n_fft"):
            await knot.process(_SIGNAL, n_mels=128, n_fft=0, hop_length=256)

    async def test_rejects_hop_exceeding_n_fft(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="hop_length"):
            await knot.process(_SIGNAL, n_mels=128, n_fft=256, hop_length=512)

    async def test_emits_spectrum_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, n_mels=128, n_fft=512, hop_length=256)
        assert isinstance(out, dict)
        assert out["n_mels"] == 128
