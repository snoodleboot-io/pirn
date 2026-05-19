"""Unit tests for :class:`ArbitraryResamplerPipeline`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.resampling.arbitrary_resampler_pipeline import ArbitraryResamplerPipeline
from pirn.domains.signal.types.signal_payload import SignalPayload
from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestArbitraryResamplerPipeline(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ArbitraryResamplerPipeline:
        return ArbitraryResamplerPipeline(
            signal=_up(),
            input_rate_hz=1000.0,
            output_rate_hz=22050.0,
            _config=KnotConfig(id="arp"),
        )

    async def test_rejects_non_positive_input_rate(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="input_rate_hz"):
            await knot.process(_SIGNAL, input_rate_hz=0.0, output_rate_hz=22050.0)

    async def test_rejects_non_positive_output_rate(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="output_rate_hz"):
            await knot.process(_SIGNAL, input_rate_hz=1000.0, output_rate_hz=0.0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, input_rate_hz=1000.0, output_rate_hz=22050.0)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:resampled"
        assert out.frame.sample_rate_hz == 22050.0
