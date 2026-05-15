"""Unit tests for :class:`ICARobustDecomposer`."""

from __future__ import annotations

import unittest

try:
    import sklearn  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("sklearn not installed") from _e

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import numpy as np
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.separation.ica_robust_decomposer import ICARobustDecomposer
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.source_payload import SourcePayload

_rng = np.random.default_rng(0)
_SIGNAL = SignalPayload(
    metadata=SignalFrame(signal_id="test", channel_count=8, sample_rate_hz=1000.0, samples_per_channel=1024),
    data=_rng.standard_normal((8, 1024)),
)


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestICARobustDecomposer(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ICARobustDecomposer:
        return ICARobustDecomposer(
            signal=_up(),
            source_count=3,
            contamination_fraction=0.1,
            _config=KnotConfig(id="rica"),
        )

    async def test_rejects_non_positive_source_count(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="source_count"):
            await knot.process(_SIGNAL, source_count=0, contamination_fraction=0.1)

    async def test_rejects_contamination_ge_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="contamination_fraction"):
            await knot.process(_SIGNAL, source_count=3, contamination_fraction=1.0)

    async def test_emits_source_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, source_count=3, contamination_fraction=0.1)
        assert isinstance(out, SourcePayload)
        assert out.frame.source_count == 3
