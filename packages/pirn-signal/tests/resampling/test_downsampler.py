"""Unit tests for :class:`Downsampler`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.resampling.downsampler import Downsampler
from pirn_signal.types.signal_payload import SignalPayload

from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


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
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:downsample"
        assert out.frame.sample_rate_hz == 250.0
