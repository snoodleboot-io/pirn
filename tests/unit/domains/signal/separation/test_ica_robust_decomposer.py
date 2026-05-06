"""Unit tests for :class:`ICARobustDecomposer`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.separation.ica_robust_decomposer import ICARobustDecomposer
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.source_frame import SourceFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestICARobustDecomposer(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ICARobustDecomposer:
        return ICARobustDecomposer(
            signal=_up(),
            source_count=3,
            contamination_fraction=0.1,
            _config=KnotConfig(id="rica"),
        )

    async def test_rejects_non_positive_source_count(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="source_count"):
            await knot.process(_SIGNAL, source_count=0, contamination_fraction=0.1)

    async def test_rejects_contamination_ge_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="contamination_fraction"):
            await knot.process(_SIGNAL, source_count=3, contamination_fraction=1.0)

    async def test_emits_source_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, source_count=3, contamination_fraction=0.1)
        assert isinstance(out, SourceFrame)
        assert out.source_count == 3
