"""Unit tests for :class:`PolyphaseResampler`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.resampling.polyphase_resampler import PolyphaseResampler
from pirn.domains.signal.types.signal_payload import SignalPayload
from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestPolyphaseResampler(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> PolyphaseResampler:
        return PolyphaseResampler(
            signal=_up(),
            upsample_factor=3,
            downsample_factor=2,
            filter_length=32,
            _config=KnotConfig(id="pr"),
        )

    async def test_rejects_non_positive_upsample_factor(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="upsample_factor"):
            await knot.process(_SIGNAL, upsample_factor=0, downsample_factor=2, filter_length=32)

    async def test_rejects_non_positive_downsample_factor(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="downsample_factor"):
            await knot.process(_SIGNAL, upsample_factor=3, downsample_factor=0, filter_length=32)

    async def test_rejects_non_positive_filter_length(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="filter_length"):
            await knot.process(_SIGNAL, upsample_factor=3, downsample_factor=2, filter_length=0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, upsample_factor=3, downsample_factor=2, filter_length=32)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:polyphase"
        assert out.frame.sample_rate_hz == 1500.0
