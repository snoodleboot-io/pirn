"""Unit tests for :class:`OnsetDetector`."""

from __future__ import annotations

import unittest

try:
    import librosa  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("librosa not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.audio.onset_detector import OnsetDetector
from pirn_signal.types.signal_payload import SignalPayload

from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestOnsetDetector(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> OnsetDetector:
        return OnsetDetector(
            signal=_up(),
            hop_length=512,
            _config=KnotConfig(id="od"),
        )

    async def test_rejects_non_positive_hop_length(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="hop_length"):
            await knot.process(_SIGNAL, hop_length=0)

    async def test_rejects_non_positive_threshold(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="threshold"):
            await knot.process(_SIGNAL, hop_length=512, threshold=0.0)

    async def test_emits_mapping(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, hop_length=512, threshold=0.5)
        assert isinstance(out, dict)
        assert "onset_times_sec" in out
        assert "signal_id" in out
