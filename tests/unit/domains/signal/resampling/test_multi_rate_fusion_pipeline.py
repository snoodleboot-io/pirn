"""Unit tests for :class:`MultiRateFusionPipeline`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.resampling.multi_rate_fusion_pipeline import MultiRateFusionPipeline
from pirn.domains.signal.types.signal_payload import SignalPayload
from tests.unit.domains.signal.conftest import make_signal_payload

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
        assert out.frame.sample_rate_hz == 2000.0
