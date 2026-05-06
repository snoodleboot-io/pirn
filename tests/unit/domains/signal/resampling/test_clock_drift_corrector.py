"""Unit tests for :class:`ClockDriftCorrector`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.resampling.clock_drift_corrector import ClockDriftCorrector
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestClockDriftCorrector(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ClockDriftCorrector:
        return ClockDriftCorrector(
            signal=_up(),
            reference_rate_hz=1000.0,
            measured_rate_hz=999.5,
            _config=KnotConfig(id="cdc"),
        )

    async def test_rejects_non_positive_reference_rate(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="reference_rate_hz"):
            await knot.process(_SIGNAL, reference_rate_hz=0.0, measured_rate_hz=999.5)

    async def test_rejects_non_positive_measured_rate(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="measured_rate_hz"):
            await knot.process(_SIGNAL, reference_rate_hz=1000.0, measured_rate_hz=0.0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, reference_rate_hz=1000.0, measured_rate_hz=999.5)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:drift_corrected"
