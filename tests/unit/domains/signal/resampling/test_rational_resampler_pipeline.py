"""Unit tests for :class:`RationalResamplerPipeline`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.resampling.rational_resampler_pipeline import RationalResamplerPipeline
from pirn_signal.types.signal_payload import SignalPayload

from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestRationalResamplerPipeline(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> RationalResamplerPipeline:
        return RationalResamplerPipeline(
            signal=_up(),
            upsample_factor=3,
            downsample_factor=2,
            _config=KnotConfig(id="rrp"),
        )

    async def test_rejects_non_positive_upsample_factor(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="upsample_factor"):
            await knot.process(_SIGNAL, upsample_factor=0, downsample_factor=2)

    async def test_rejects_non_positive_downsample_factor(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="downsample_factor"):
            await knot.process(_SIGNAL, upsample_factor=3, downsample_factor=0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, upsample_factor=3, downsample_factor=2)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:rational"
        assert out.frame.sample_rate_hz == 1500.0
