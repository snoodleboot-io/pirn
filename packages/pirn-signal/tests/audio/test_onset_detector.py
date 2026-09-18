"""Unit tests for :class:`OnsetDetector`."""

from __future__ import annotations

import unittest

try:
    import librosa  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("librosa not installed") from _e

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.audio.onset_detector import OnsetDetector
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

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

    async def test_emits_feature_payload(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, hop_length=512, threshold=0.5)
        assert isinstance(out, FeaturePayload)
        assert out.data.shape[0] == 1

    async def test_multichannel_computes_per_channel(self) -> None:
        knot = self._make()
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=2048)
        out = await knot.process(multichannel, hop_length=512, threshold=0.5)
        assert isinstance(out, FeaturePayload)
        assert out.metadata.channel_count == 2
        assert out.data.shape[0] == 2


class TestThresholdIsApplied(unittest.IsolatedAsyncioTestCase):
    """``threshold`` is the peak-picking threshold, not a validated no-op."""

    @staticmethod
    def _loud_and_quiet_onsets(sample_rate_hz: float = 22050.0):
        """Four loud clicks with three faint ones between them."""
        sample_count = int(6.0 * sample_rate_hz)
        data = np.zeros(sample_count)
        click = np.hanning(int(0.005 * sample_rate_hz))
        for index, start_sec in enumerate([0.5, 1.5, 2.5, 3.5, 4.5, 5.0, 5.5]):
            start = int(start_sec * sample_rate_hz)
            amplitude = 1.0 if index % 2 == 0 else 0.02
            data[start : start + click.size] += amplitude * click
        return make_signal_payload(
            sample_rate_hz=sample_rate_hz, samples_per_channel=sample_count
        ).derive("clicks", data)

    def _knot(self) -> OnsetDetector:
        return OnsetDetector(signal=_up(), hop_length=512, _config=KnotConfig(id="od"))

    async def test_a_higher_threshold_keeps_only_the_strong_onsets(self) -> None:
        # Arrange
        payload = self._loud_and_quiet_onsets()

        # Act
        permissive = await self._knot().process(payload, hop_length=512, threshold=0.05)
        strict = await self._knot().process(payload, hop_length=512, threshold=5.0)

        # Assert: the strict threshold detects strictly fewer onsets.
        permissive_count = int(np.count_nonzero(~np.isnan(permissive.data[0])))
        strict_count = int(np.count_nonzero(~np.isnan(strict.data[0])))
        assert strict_count < permissive_count, (strict_count, permissive_count)
        assert strict_count >= 1
