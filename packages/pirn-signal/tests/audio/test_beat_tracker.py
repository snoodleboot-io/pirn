"""Unit tests for :class:`BeatTracker`."""

from __future__ import annotations

import unittest

try:
    import librosa  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("librosa not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.audio.beat_tracker import BeatTracker
from pirn_signal.types.signal_payload import SignalPayload

from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestBeatTracker(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> BeatTracker:
        return BeatTracker(
            signal=_up(),
            hop_length=512,
            _config=KnotConfig(id="bt"),
        )

    async def test_rejects_non_positive_hop_length(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="hop_length"):
            await knot.process(_SIGNAL, hop_length=0)

    async def test_rejects_non_positive_tempo_min(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="tempo_min_bpm"):
            await knot.process(_SIGNAL, hop_length=512, tempo_min_bpm=0.0)

    async def test_rejects_tempo_max_le_min(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="tempo_max_bpm"):
            await knot.process(_SIGNAL, hop_length=512, tempo_min_bpm=120.0, tempo_max_bpm=60.0)

    async def test_emits_mapping(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, hop_length=512)
        assert isinstance(out, dict)
        assert "tempo_bpm" in out
        assert "beat_frames" in out
