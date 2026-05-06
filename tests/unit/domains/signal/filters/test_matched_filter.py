"""Unit tests for :class:`MatchedFilter`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.filters.matched_filter import MatchedFilter
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestMatchedFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> MatchedFilter:
        return MatchedFilter(
            signal=_up(),
            template=(1.0, 0.5, 0.0, -0.5, -1.0),
            _config=KnotConfig(id="mf"),
        )

    async def test_rejects_empty_template(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="template"):
            await knot.process(_SIGNAL, template=())

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, template=(1.0, 0.5, 0.0, -0.5, -1.0))
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:matched"
