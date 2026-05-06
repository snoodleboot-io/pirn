"""Unit tests for :class:`NMFDecomposer`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.separation.nmf_decomposer import NMFDecomposer
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.source_frame import SourceFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestNMFDecomposer(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> NMFDecomposer:
        return NMFDecomposer(
            signal=_up(),
            component_count=4,
            _config=KnotConfig(id="nmf"),
        )

    async def test_rejects_non_positive_component_count(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="component_count"):
            await knot.process(_SIGNAL, component_count=0)

    async def test_rejects_non_positive_max_iterations(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="max_iterations"):
            await knot.process(_SIGNAL, component_count=4, max_iterations=0)

    async def test_emits_source_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, component_count=4)
        assert isinstance(out, SourceFrame)
        assert out.source_count == 4
