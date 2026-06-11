"""Unit tests for :class:`ArtifactRemover`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

try:
    import sklearn  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("sklearn not installed") from _e

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.artifact_remover import ArtifactRemover
from pirn.domains.health.types.health_signal_frame import HealthSignalFrame
from pirn.domains.health.types.health_signal_payload import HealthSignalPayload

_CFG = KnotConfig(id="r")
_SIGNAL = HealthSignalPayload(
    metadata=HealthSignalFrame(signal_id="s", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512),
    data=np.random.default_rng(0).standard_normal((2, 512)),
)
_KNOT = ArtifactRemover(signal=_SIGNAL, n_components=10, method="infomax", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "HealthSignalPayload"):
            await _KNOT.process(signal="x", n_components=10, method="infomax")  # type: ignore[arg-type]

    async def test_rejects_non_int_components(self) -> None:
        with self.assertRaisesRegex(TypeError, "n_components"):
            await _KNOT.process(signal=_SIGNAL, n_components="x", method="infomax")  # type: ignore[arg-type]

    async def test_rejects_non_positive_components(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            await _KNOT.process(signal=_SIGNAL, n_components=0, method="infomax")

    async def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            await _KNOT.process(signal=_SIGNAL, n_components=10, method="bogus")

    async def test_returns_signal_payload(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, n_components=10, method="fastica")
        assert isinstance(out, HealthSignalPayload)
