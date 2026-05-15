"""Unit tests for :class:`SparseDecomposer`."""

from __future__ import annotations

import unittest

try:
    import sklearn  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("sklearn not installed") from _e

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.separation.sparse_decomposer import SparseDecomposer
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.source_payload import SourcePayload
from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload(channel_count=8)


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


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
        assert isinstance(out, SourcePayload)
        assert out.frame.source_count == 8
