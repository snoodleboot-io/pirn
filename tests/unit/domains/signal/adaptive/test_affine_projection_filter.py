"""Unit tests for :class:`AffineProjectionFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.adaptive.affine_projection_filter import AffineProjectionFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()
_REF = make_signal_frame(signal_id="reference")


def _upstream(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestAffineProjectionFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> AffineProjectionFilter:
        return AffineProjectionFilter(
            signal=_upstream("signal"),
            reference=_upstream("reference"),
            filter_length=8,
            projection_order=2,
            step_size=0.1,
            _config=KnotConfig(id="apa"),
        )

    async def test_rejects_non_positive_filter_length(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="filter_length"):
            await knot.process(_SIGNAL, _REF, filter_length=0, projection_order=2, step_size=0.1)

    async def test_rejects_non_positive_projection_order(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="projection_order"):
            await knot.process(_SIGNAL, _REF, filter_length=8, projection_order=0, step_size=0.1)

    async def test_rejects_non_positive_step_size(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="step_size"):
            await knot.process(_SIGNAL, _REF, filter_length=8, projection_order=2, step_size=0.0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, _REF, filter_length=8, projection_order=2, step_size=0.1)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:apa"
