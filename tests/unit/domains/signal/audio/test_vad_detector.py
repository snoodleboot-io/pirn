"""Unit tests for :class:`VADDetector`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.audio.vad_detector import VADDetector
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestVADDetector(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> VADDetector:
        return VADDetector(
            signal=_up(),
            frame_duration_ms=20,
            aggressiveness=2,
            _config=KnotConfig(id="vad"),
        )

    async def test_rejects_invalid_frame_duration(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="frame_duration_ms"):
            await knot.process(_SIGNAL, frame_duration_ms=15, aggressiveness=2)

    async def test_rejects_aggressiveness_above_three(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="aggressiveness"):
            await knot.process(_SIGNAL, frame_duration_ms=20, aggressiveness=4)

    async def test_rejects_negative_aggressiveness(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="aggressiveness"):
            await knot.process(_SIGNAL, frame_duration_ms=20, aggressiveness=-1)

    async def test_emits_segment_list(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, frame_duration_ms=20, aggressiveness=2)
        assert isinstance(out, list)
        assert all("is_speech" in seg for seg in out)
