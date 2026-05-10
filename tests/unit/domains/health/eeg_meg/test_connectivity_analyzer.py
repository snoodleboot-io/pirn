"""Unit tests for :class:`ConnectivityAnalyzer`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.connectivity_analyzer import (
    ConnectivityAnalyzer,
)
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.types.signal_payload import SignalPayload

_CFG = KnotConfig(id="c")
_SIGNAL = SignalPayload(
    metadata=SignalFrame(signal_id="s", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512),
    data=np.random.default_rng(0).standard_normal((2, 512)),
)
_KNOT = ConnectivityAnalyzer(signal=_SIGNAL, channel_names=[], method="plv", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalPayload"):
            await _KNOT.process(signal="x", channel_names=[], method="plv")  # type: ignore[arg-type]

    async def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "channel_names"):
            await _KNOT.process(signal=_SIGNAL, channel_names=42, method="plv")  # type: ignore[arg-type]

    async def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            await _KNOT.process(signal=_SIGNAL, channel_names=[], method="bogus")

    async def test_returns_matrix(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, channel_names=["ch0", "ch1"], method="plv")
        assert isinstance(out, Mapping)
        assert "ch0" in out
