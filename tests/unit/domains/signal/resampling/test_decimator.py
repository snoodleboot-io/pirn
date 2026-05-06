"""Unit tests for :class:`Decimator`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.resampling.decimator import Decimator
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestDecimator(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> Decimator:
        return Decimator(
            signal=_up(),
            decimation_factor=2,
            _config=KnotConfig(id="d"),
        )

    async def test_rejects_decimation_factor_le_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="decimation_factor"):
            await knot.process(_SIGNAL, decimation_factor=1)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, decimation_factor=2)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:decimate"
        assert out.sample_rate_hz == 500.0
