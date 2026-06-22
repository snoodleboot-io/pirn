"""Unit tests for :class:`MatchedFilter`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.filters.matched_filter import MatchedFilter
from pirn_signal.types.signal_payload import SignalPayload

from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


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
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:matched"
