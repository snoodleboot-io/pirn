"""Unit tests for :class:`BeamformerMUSIC`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.beamforming.beamformer_music import BeamformerMUSIC
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestBeamformerMUSIC(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> BeamformerMUSIC:
        return BeamformerMUSIC(
            signal=_up(),
            num_elements=8,
            num_sources=2,
            angle_scan_deg=(-90.0, 90.0, 1.0),
            _config=KnotConfig(id="music"),
        )

    async def test_rejects_non_positive_num_elements(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="num_elements"):
            await knot.process(_SIGNAL, num_elements=0, num_sources=2, angle_scan_deg=(-90.0, 90.0, 1.0))

    async def test_rejects_non_positive_num_sources(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="num_sources"):
            await knot.process(_SIGNAL, num_elements=8, num_sources=0, angle_scan_deg=(-90.0, 90.0, 1.0))

    async def test_rejects_zero_step(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="step"):
            await knot.process(_SIGNAL, num_elements=8, num_sources=2, angle_scan_deg=(-90.0, 90.0, 0.0))

    async def test_emits_spectrum_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, num_elements=8, num_sources=2, angle_scan_deg=(-90.0, 90.0, 1.0))
        assert isinstance(out, SpectrumFrame)
