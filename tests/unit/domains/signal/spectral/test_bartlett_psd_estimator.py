"""Unit tests for :class:`BartlettPSDEstimator`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.spectral.bartlett_psd_estimator import BartlettPSDEstimator
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestBartlettPSDEstimator(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> BartlettPSDEstimator:
        return BartlettPSDEstimator(
            signal=_up(),
            num_segments=4,
            _config=KnotConfig(id="bpsd"),
        )

    async def test_rejects_non_positive_num_segments(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="num_segments"):
            await knot.process(_SIGNAL, num_segments=0)

    async def test_emits_spectrum_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, num_segments=4)
        assert isinstance(out, SpectrumFrame)
        assert out.signal_id == "test"
