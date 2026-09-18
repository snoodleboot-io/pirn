"""Tests for :class:`CrossValidator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_ml.data_prep.cross_validator import CrossValidator
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


@KnotFactory.knot
async def emit_dataset() -> DatasetManifest:
    return DatasetManifest(
        name="customers",
        feature_names=("a",),
        row_count=100,
        source_uri="db://x",
    )


def _make_dataset(row_count: int = 100) -> DatasetManifest:
    return DatasetManifest(
        name="customers",
        feature_names=("a",),
        row_count=row_count,
        source_uri="db://x",
    )


class TestCrossValidatorHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_k_folds(self) -> None:
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            CrossValidator(
                dataset=dataset,
                k=5,
                random_seed=42,
                _config=KnotConfig(id="cv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out: tuple[SplitManifest, ...] = result.outputs["cv"]
        assert isinstance(out, tuple)
        assert len(out) == 5
        for split in out:
            assert isinstance(split, SplitManifest)
            assert split.validation is None
            assert split.train.row_count + split.test.row_count == 100


class TestCrossValidatorProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> CrossValidator:
        with Tapestry():
            k = CrossValidator.__new__(CrossValidator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        return k

    async def test_rejects_k_below_two(self) -> None:
        k_knot = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k_knot.process(dataset=_make_dataset(), k=1)

    async def test_rejects_k_not_int(self) -> None:
        k_knot = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k_knot.process(dataset=_make_dataset(), k="five")  # type: ignore[arg-type]

    async def test_rejects_row_count_less_than_k(self) -> None:
        k_knot = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k_knot.process(dataset=_make_dataset(row_count=1), k=5)


class TestCrossValidatorRowPartition(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> CrossValidator:
        with Tapestry():
            k = CrossValidator.__new__(CrossValidator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        return k

    async def test_folds_partition_rows_and_train_is_the_complement(self) -> None:
        folds = await self._make_knot().process(dataset=_make_dataset(row_count=23), k=4)
        test_rows = sorted(row for fold in folds for row in fold.test.row_indices)
        assert test_rows == list(range(23))
        assert sorted(fold.test.row_count for fold in folds) == [5, 6, 6, 6]
        for fold in folds:
            assert set(fold.train.row_indices) == set(range(23)) - set(fold.test.row_indices)
            assert fold.train.row_count == len(fold.train.row_indices)

    async def test_random_seed_drives_a_reproducible_shuffle(self) -> None:
        knot = self._make_knot()
        first = await knot.process(dataset=_make_dataset(), k=5, random_seed=1)
        again = await knot.process(dataset=_make_dataset(), k=5, random_seed=1)
        other = await knot.process(dataset=_make_dataset(), k=5, random_seed=2)
        rows = [fold.test.row_indices for fold in first]
        assert rows == [fold.test.row_indices for fold in again]
        assert rows != [fold.test.row_indices for fold in other]
        # Shuffled, not contiguous blocks of the source order.
        assert rows[0] != tuple(range(20))
