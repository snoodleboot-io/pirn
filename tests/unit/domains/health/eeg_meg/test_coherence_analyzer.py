"""Unit tests for :class:`CoherenceAnalyzer`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.coherence_analyzer import CoherenceAnalyzer
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.types.signal_payload import SignalPayload

_CFG = KnotConfig(id="c")
_SIGNAL = SignalPayload(
    frame=SignalFrame(signal_id="s", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512),
    data=np.random.default_rng(0).standard_normal((2, 512)),
)
_KNOT = CoherenceAnalyzer(signal=_SIGNAL, channel_pairs=[("ch0", "ch1")], band_low_hz=1.0, band_high_hz=10.0, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalPayload"):
            await _KNOT.process(signal="x", channel_pairs=[], band_low_hz=1.0, band_high_hz=10.0)  # type: ignore[arg-type]

    async def test_rejects_non_sequence_pairs(self) -> None:
        with self.assertRaisesRegex(TypeError, "channel_pairs"):
            await _KNOT.process(signal=_SIGNAL, channel_pairs=42, band_low_hz=1.0, band_high_hz=10.0)  # type: ignore[arg-type]

    async def test_rejects_invalid_pair(self) -> None:
        with self.assertRaisesRegex(TypeError, r"\(str, str\)"):
            await _KNOT.process(signal=_SIGNAL, channel_pairs=[(1, 2)], band_low_hz=1.0, band_high_hz=10.0)  # type: ignore[list-item]

    async def test_rejects_low_ge_high(self) -> None:
        with self.assertRaisesRegex(ValueError, "<"):
            await _KNOT.process(signal=_SIGNAL, channel_pairs=[], band_low_hz=10.0, band_high_hz=10.0)

    async def test_returns_per_pair_mapping(self) -> None:
        out = await _KNOT.process(
            signal=_SIGNAL,
            channel_pairs=[("ch0", "ch1")],
            band_low_hz=8.0,
            band_high_hz=13.0,
        )
        assert isinstance(out, Mapping)
        assert ("ch0", "ch1") in out
