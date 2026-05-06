"""Unit tests for :class:`BeamformerMVDR`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.beamforming.beamformer_mvdr import BeamformerMVDR
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestBeamformerMVDR(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> BeamformerMVDR:
        return BeamformerMVDR(
            signal=_up(),
            num_elements=8,
            steering_angle_deg=30.0,
            _config=KnotConfig(id="mvdr"),
        )

    async def test_rejects_non_positive_num_elements(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="num_elements"):
            await knot.process(_SIGNAL, num_elements=0, steering_angle_deg=30.0)

    async def test_rejects_negative_diagonal_loading(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="diagonal_loading"):
            await knot.process(_SIGNAL, num_elements=8, steering_angle_deg=30.0, diagonal_loading=-1.0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, num_elements=8, steering_angle_deg=30.0)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:mvdr"
