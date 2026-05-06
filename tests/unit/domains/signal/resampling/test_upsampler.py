"""Unit tests for :class:`Upsampler`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.resampling.upsampler import Upsampler
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestUpsampler(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> Upsampler:
        return Upsampler(
            signal=_up(),
            upsample_factor=4,
            _config=KnotConfig(id="ups"),
        )

    async def test_rejects_upsample_factor_le_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="upsample_factor"):
            await knot.process(_SIGNAL, upsample_factor=1)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, upsample_factor=4)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:upsample"
        assert out.sample_rate_hz == 4000.0
