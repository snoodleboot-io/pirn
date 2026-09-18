"""Unit tests for :class:`ArbitraryResamplerPipeline`."""

from __future__ import annotations

import math
import unittest

import numpy as np

try:
    import scipy  # noqa: F401  # imported only to skip when scipy is absent
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.resampling.arbitrary_resampler_pipeline import ArbitraryResamplerPipeline
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

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
        assert out.metadata.signal_id == "test:resampled"
        assert out.metadata.sample_rate_hz == 22050.0

    async def test_fractional_rates_resample_at_their_exact_ratio(self) -> None:
        # Arrange: 999.5 Hz -> 1000 Hz is exactly 2000/1999; the integer parts (999, 1000)
        # would give 1000/999 instead.
        knot = self._make()
        count = 19990
        tone_hz = 7.0
        payload = SignalPayload(
            metadata=make_signal_payload(sample_rate_hz=999.5, samples_per_channel=count).metadata,
            data=np.sin(2 * np.pi * tone_hz * np.arange(count) / 999.5),
        )

        # Act
        out = await knot.process(payload, input_rate_hz=999.5, output_rate_hz=1000.0)

        # Assert
        assert out.data.shape[-1] == math.ceil(count * 2000 / 1999)
        expected = np.sin(2 * np.pi * tone_hz * np.arange(out.data.shape[-1]) / 1000.0)
        interior = slice(500, -500)
        np.testing.assert_allclose(out.data[interior], expected[interior], atol=1e-2)
