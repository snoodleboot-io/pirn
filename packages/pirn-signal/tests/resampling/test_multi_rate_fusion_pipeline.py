"""Unit tests for :class:`MultiRateFusionPipeline`."""

from __future__ import annotations

import unittest

import numpy as np

try:
    import scipy  # noqa: F401  # imported only to skip when scipy is absent
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.resampling.multi_rate_fusion_pipeline import MultiRateFusionPipeline
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL_A = make_signal_payload()
_SIGNAL_B = make_signal_payload(signal_id="b")


def _up(name: str) -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestMultiRateFusionPipeline(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> MultiRateFusionPipeline:
        return MultiRateFusionPipeline(
            signal_a=_up("signal_a"),
            signal_b=_up("signal_b"),
            output_rate_hz=2000.0,
            _config=KnotConfig(id="mrf"),
        )

    async def test_rejects_non_positive_output_rate(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="output_rate_hz"):
            await knot.process(_SIGNAL_A, _SIGNAL_B, output_rate_hz=0.0)

    async def test_emits_tuple_of_signal_frames(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL_A, _SIGNAL_B, output_rate_hz=2000.0)
        assert isinstance(out, SignalPayload)
        assert out.metadata.sample_rate_hz == 2000.0

    async def test_fractional_input_rates_resample_at_their_exact_ratio(self) -> None:
        # Arrange: the same 5 Hz tone captured at 999.5 Hz and at 500.25 Hz. Truncating
        # the rates to integers (999, 500) would stretch each by ~0.05 % and misalign
        # them; resampled at the exact ratios they coincide on the 1000 Hz grid.
        knot = self._make()
        tone_hz = 5.0
        duration_s = 20.0
        payloads: list[SignalPayload] = []
        for rate_hz, signal_id in ((999.5, "a"), (500.25, "b")):
            count = int(duration_s * rate_hz)
            payloads.append(
                SignalPayload(
                    metadata=make_signal_payload(
                        signal_id=signal_id, sample_rate_hz=rate_hz, samples_per_channel=count
                    ).metadata,
                    data=np.sin(2 * np.pi * tone_hz * np.arange(count) / rate_hz),
                )
            )

        # Act
        out = await knot.process(payloads[0], payloads[1], output_rate_hz=1000.0)

        # Assert: the fused tone is the 5 Hz tone on the 1000 Hz grid, interior samples.
        expected = np.sin(2 * np.pi * tone_hz * np.arange(out.data.shape[-1]) / 1000.0)
        interior = slice(1000, -1000)
        np.testing.assert_allclose(out.data[interior], expected[interior], atol=1e-2)
