"""Unit tests for :class:`ConnectivityAnalyzer`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

from collections.abc import Mapping

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.connectivity_analyzer import (
    ConnectivityAnalyzer,
)
from pirn.domains.health.types.health_signal_frame import HealthSignalFrame
from pirn.domains.health.types.health_signal_payload import HealthSignalPayload

_CFG = KnotConfig(id="c")
_SIGNAL = HealthSignalPayload(
    metadata=HealthSignalFrame(signal_id="s", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512),
    data=np.random.default_rng(0).standard_normal((2, 512)),
)
_KNOT = ConnectivityAnalyzer(signal=_SIGNAL, channel_names=[], method="plv", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "HealthSignalPayload"):
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
