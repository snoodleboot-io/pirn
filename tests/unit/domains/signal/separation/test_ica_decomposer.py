"""Unit tests for :class:`ICADecomposer`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.separation.ica_decomposer import ICADecomposer
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.source_frame import SourceFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestICADecomposer(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ICADecomposer:
        return ICADecomposer(
            signal=_up(),
            source_count=3,
            _config=KnotConfig(id="ica"),
        )

    async def test_rejects_non_positive_source_count(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="source_count"):
            await knot.process(_SIGNAL, source_count=0)

    async def test_emits_source_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, source_count=3)
        assert isinstance(out, SourceFrame)
        assert out.source_count == 3
