"""Unit tests for :class:`SparseDecomposer`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.separation.sparse_decomposer import SparseDecomposer
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.source_frame import SourceFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestSparseDecomposer(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> SparseDecomposer:
        return SparseDecomposer(
            signal=_up(),
            atom_count=8,
            sparsity_target=3,
            _config=KnotConfig(id="sd"),
        )

    async def test_rejects_non_positive_atom_count(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="atom_count"):
            await knot.process(_SIGNAL, atom_count=0, sparsity_target=3)

    async def test_rejects_non_positive_sparsity_target(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="sparsity_target"):
            await knot.process(_SIGNAL, atom_count=8, sparsity_target=0)

    async def test_rejects_unknown_algorithm(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="algorithm"):
            await knot.process(_SIGNAL, atom_count=8, sparsity_target=3, algorithm="bogus")

    async def test_emits_source_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, atom_count=8, sparsity_target=3)
        assert isinstance(out, SourceFrame)
        assert out.source_count == 3
