"""Unit tests for :class:`LMSAdaptiveFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.adaptive.lms_adaptive_filter import LMSAdaptiveFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()
_REF = make_signal_frame(signal_id="reference")


def _up(name: str) -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestLMSAdaptiveFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> LMSAdaptiveFilter:
        return LMSAdaptiveFilter(
            signal=_up("signal"),
            reference=_up("reference"),
            filter_length=8,
            step_size=0.01,
            _config=KnotConfig(id="lms"),
        )

    async def test_rejects_non_positive_filter_length(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="filter_length"):
            await knot.process(_SIGNAL, _REF, filter_length=0, step_size=0.01)

    async def test_rejects_non_positive_step_size(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="step_size"):
            await knot.process(_SIGNAL, _REF, filter_length=8, step_size=0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, _REF, filter_length=8, step_size=0.01)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:lms"
