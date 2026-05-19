"""Unit tests for :class:`EvokedResponseAverager`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.evoked_response_averager import (
    EvokedResponseAverager,
)
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.types.signal_payload import SignalPayload

_CFG = KnotConfig(id="e")
_EPOCH = SignalPayload(
    metadata=SignalFrame(signal_id="ep0", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512),
    data=np.random.default_rng(0).standard_normal((2, 512)),
)
_KNOT = EvokedResponseAverager(epochs=[_EPOCH], condition="target", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "epochs"):
            await _KNOT.process(epochs=42, condition="target")  # type: ignore[arg-type]

    async def test_rejects_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await _KNOT.process(epochs=[], condition="target")

    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalPayload"):
            await _KNOT.process(epochs=["x"], condition="target")  # type: ignore[list-item]

    async def test_rejects_empty_condition(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await _KNOT.process(epochs=[_EPOCH], condition="")

    async def test_returns_signal_payload(self) -> None:
        out = await _KNOT.process(epochs=[_EPOCH], condition="target")
        assert isinstance(out, SignalPayload)
        assert "target" in out.frame.signal_id
