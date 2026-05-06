"""Unit tests for :class:`Downsampler`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.resampling.downsampler import Downsampler
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestDownsampler(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> Downsampler:
        return Downsampler(
            signal=_up(),
            downsample_factor=4,
            _config=KnotConfig(id="ds"),
        )

    async def test_rejects_downsample_factor_le_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="downsample_factor"):
            await knot.process(_SIGNAL, downsample_factor=1)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, downsample_factor=4)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:downsample"
        assert out.sample_rate_hz == 250.0
