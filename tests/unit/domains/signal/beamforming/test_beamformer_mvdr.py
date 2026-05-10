"""Unit tests for :class:`BeamformerMVDR`."""

from __future__ import annotations

import unittest

import numpy as np
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.beamforming.beamformer_mvdr import BeamformerMVDR
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload

_rng = np.random.default_rng(42)
_SIGNAL = SignalPayload(
    metadata=SignalFrame(signal_id="test", channel_count=8, sample_rate_hz=1000.0, samples_per_channel=1024),
    data=_rng.standard_normal((8, 1024)),
)


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestBeamformerMVDR(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> BeamformerMVDR:
        return BeamformerMVDR(
            signal=_up(),
            num_elements=8,
            element_spacing_m=0.05,
            steering_angle_deg=30.0,
            _config=KnotConfig(id="mvdr"),
        )

    async def test_rejects_non_positive_num_elements(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="num_elements"):
            await knot.process(_SIGNAL, num_elements=0, element_spacing_m=0.05, steering_angle_deg=30.0)

    async def test_rejects_negative_diagonal_loading(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="diagonal_loading"):
            await knot.process(_SIGNAL, num_elements=8, element_spacing_m=0.05, steering_angle_deg=30.0, diagonal_loading=-1.0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, num_elements=8, element_spacing_m=0.05, steering_angle_deg=30.0)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:mvdr"
