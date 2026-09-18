"""Unit tests for :class:`ArtifactRemover`."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

try:
    import scipy  # noqa: F401  # imported only to skip when scipy is absent
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

try:
    import sklearn  # noqa: F401  # imported only to skip when sklearn is absent
except ImportError as _e:
    raise unittest.SkipTest("sklearn not installed") from _e

import numpy as np
from pirn.core.knot_config import KnotConfig

from pirn_health.eeg_meg.artifact_remover import ArtifactRemover
from pirn_health.types.health_signal_frame import HealthSignalFrame
from pirn_health.types.health_signal_payload import HealthSignalPayload

_CFG = KnotConfig(id="r")
_SIGNAL = HealthSignalPayload(
    metadata=HealthSignalFrame(
        signal_id="s", channel_count=2, sample_rate_hz=256.0, samples_per_channel=512
    ),
    # Two non-Gaussian sources (sine, square wave) mixed into two channels: an
    # identifiable ICA problem, so FastICA converges with n_components == channels.
    data=np.array([[1.0, 0.6], [0.4, 1.0]])
    @ np.stack(
        [
            np.sin(np.linspace(0.0, 16.0, 512)),
            np.sign(np.sin(np.linspace(0.0, 23.0, 512))),
        ]
    ),
)
_KNOT = ArtifactRemover(signal=_SIGNAL, n_components=2, method="infomax", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "HealthSignalPayload"):
            await _KNOT.process(signal="x", n_components=10, method="infomax")

    async def test_rejects_non_int_components(self) -> None:
        with self.assertRaisesRegex(TypeError, "n_components"):
            await _KNOT.process(signal=_SIGNAL, n_components="x", method="infomax")

    async def test_rejects_non_positive_components(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            await _KNOT.process(signal=_SIGNAL, n_components=0, method="infomax")

    async def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            await _KNOT.process(signal=_SIGNAL, n_components=10, method="bogus")

    async def test_returns_signal_payload(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, n_components=2, method="fastica")
        assert isinstance(out, HealthSignalPayload)
        np.testing.assert_allclose(out.data, _SIGNAL.data, atol=1e-8)

    async def test_raises_install_hint_without_sdk(self) -> None:
        with patch.dict(sys.modules, {"sklearn.decomposition": None}):
            with self.assertRaisesRegex(ImportError, r"pirn-health\[health\]"):
                await _KNOT.process(signal=_SIGNAL, n_components=2, method="fastica")
