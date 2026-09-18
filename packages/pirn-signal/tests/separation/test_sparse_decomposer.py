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

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.separation.sparse_decomposer import SparseDecomposer
from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.source_payload import SourcePayload
from tests.conftest import make_signal_payload

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
        assert out.metadata.source_count == 8


class TestPursuitAlgorithmIsUsed(unittest.IsolatedAsyncioTestCase):
    """``algorithm`` selects a real pursuit; ``sparsity_target`` caps the non-zeros."""

    @staticmethod
    def _signal() -> SignalPayload:
        rng = np.random.default_rng(7)
        atoms = rng.standard_normal((6, 4))
        codes = np.zeros((4, 200))
        for column in range(200):
            rows = rng.choice(4, size=2, replace=False)
            codes[rows, column] = rng.standard_normal(2)
        data = atoms @ codes
        return make_signal_payload(channel_count=6, samples_per_channel=200).derive("mix", data)

    def _knot(self) -> SparseDecomposer:
        return SparseDecomposer(
            signal=_up(),
            atom_count=4,
            sparsity_target=1,
            algorithm="omp",
            _config=KnotConfig(id="sd"),
        )

    async def test_omp_respects_the_sparsity_target(self) -> None:
        # Arrange
        payload = self._signal()

        # Act
        out = await self._knot().process(
            signal=payload, atom_count=4, sparsity_target=1, algorithm="omp"
        )

        # Assert: at most one non-zero atom per time sample, which the previous
        # SparsePCA implementation never guaranteed.
        codes = np.asarray(out.data, dtype=float)
        nonzeros = np.count_nonzero(np.abs(codes) > 1e-12, axis=0)
        assert int(nonzeros.max()) <= 1, int(nonzeros.max())

    async def test_a_larger_sparsity_target_allows_more_non_zeros(self) -> None:
        payload = self._signal()
        knot = self._knot()

        tight = await knot.process(signal=payload, atom_count=4, sparsity_target=1, algorithm="omp")
        loose = await knot.process(signal=payload, atom_count=4, sparsity_target=3, algorithm="omp")

        tight_count = int(np.count_nonzero(np.abs(np.asarray(tight.data)) > 1e-12))
        loose_count = int(np.count_nonzero(np.abs(np.asarray(loose.data)) > 1e-12))
        assert loose_count > tight_count

    async def test_each_pursuit_gives_its_own_codes(self) -> None:
        payload = self._signal()
        knot = self._knot()
        results = {}
        for algorithm in ("omp", "lars", "lasso"):
            out = await knot.process(
                signal=payload, atom_count=4, sparsity_target=2, algorithm=algorithm
            )
            results[algorithm] = np.asarray(out.data, dtype=float)

        assert not np.allclose(results["omp"], results["lasso"])
