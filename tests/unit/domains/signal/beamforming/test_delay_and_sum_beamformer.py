"""Unit tests for :class:`DelayAndSumBeamformer`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.beamforming.delay_and_sum_beamformer import DelayAndSumBeamformer
from pirn_signal.types.signal_payload import SignalPayload

from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload(channel_count=8)


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestDelayAndSumBeamformer(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> DelayAndSumBeamformer:
        return DelayAndSumBeamformer(
            signal=_up(),
            num_elements=8,
            element_spacing_m=0.05,
            steering_angle_deg=0.0,
            _config=KnotConfig(id="das"),
        )

    async def test_rejects_non_positive_num_elements(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="num_elements"):
            await knot.process(_SIGNAL, num_elements=0, element_spacing_m=0.05, steering_angle_deg=0.0)

    async def test_rejects_non_positive_element_spacing(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="element_spacing_m"):
            await knot.process(_SIGNAL, num_elements=8, element_spacing_m=0.0, steering_angle_deg=0.0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, num_elements=8, element_spacing_m=0.05, steering_angle_deg=0.0)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:das"
