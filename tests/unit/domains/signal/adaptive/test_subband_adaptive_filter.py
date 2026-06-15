"""Unit tests for :class:`SubbandAdaptiveFilter`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.adaptive.subband_adaptive_filter import SubbandAdaptiveFilter
from pirn_signal.types.signal_payload import SignalPayload

from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()
_REF = make_signal_payload(signal_id="reference")


def _up(name: str) -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestSubbandAdaptiveFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> SubbandAdaptiveFilter:
        return SubbandAdaptiveFilter(
            signal=_up("signal"),
            reference=_up("reference"),
            subband_count=4,
            filter_length_per_band=8,
            step_size=0.1,
            _config=KnotConfig(id="sb"),
        )

    async def test_rejects_subband_count_le_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="subband_count"):
            await knot.process(_SIGNAL, _REF, subband_count=1, filter_length_per_band=8, step_size=0.1)

    async def test_rejects_non_positive_filter_length_per_band(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="filter_length_per_band"):
            await knot.process(_SIGNAL, _REF, subband_count=4, filter_length_per_band=0, step_size=0.1)

    async def test_rejects_non_positive_step_size(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="step_size"):
            await knot.process(_SIGNAL, _REF, subband_count=4, filter_length_per_band=8, step_size=0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, _REF, subband_count=4, filter_length_per_band=8, step_size=0.1)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:subband-adaptive"
