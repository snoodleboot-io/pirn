"""Tests for :class:`StratifiedCrossValidator` — folds really preserve class proportions."""

from __future__ import annotations

import unittest
from collections import Counter

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_ml.data_prep.stratified_cross_validator import StratifiedCrossValidator
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.dataset_payload import DatasetPayload
from pirn_ml.types.ml_features import MLFeatures


class _Fixtures:
    @staticmethod
    def dataset(labels: list[int]) -> DatasetPayload:
        rows = len(labels)
        features = np.column_stack([np.arange(rows, dtype=float), np.array(labels, dtype=float)])
        return DatasetPayload(
            metadata=DatasetManifest(
                name="patients",
                feature_names=("x", "label_copy"),
                target_name="y",
                row_count=rows,
            ),
            data=MLFeatures(feature_matrix=features, target_vector=np.array(labels)),
        )

    @staticmethod
    def knot() -> StratifiedCrossValidator:
        with Tapestry():
            knot = StratifiedCrossValidator.__new__(StratifiedCrossValidator)
            object.__setattr__(knot, "_config", KnotConfig(id="x"))
        return knot


class TestStratification(unittest.IsolatedAsyncioTestCase):
    async def test_every_fold_holds_the_global_class_proportion(self) -> None:
        # All 12 positives sit at the front: contiguous or unstratified folds skew badly.
        labels = [1] * 12 + [0] * 48
        folds = await _Fixtures.knot().process(
            dataset=_Fixtures.dataset(labels), stratify_column="y", k=4, random_seed=7
        )
        assert len(folds) == 4
        for fold in folds:
            counts = Counter(labels[row] for row in fold.test.row_indices)
            assert counts == Counter({0: 12, 1: 3})
            assert fold.test.row_count == 15
            assert fold.train.row_count == 45

    async def test_uneven_classes_stay_within_one_row_per_fold(self) -> None:
        labels = [0] * 7 + [1] * 11 + [2] * 5
        folds = await _Fixtures.knot().process(
            dataset=_Fixtures.dataset(labels), stratify_column="y", k=3
        )
        totals = Counter(labels)
        for fold in folds:
            counts = Counter(labels[row] for row in fold.test.row_indices)
            for label, total in totals.items():
                assert total // 3 <= counts[label] <= -(-total // 3)
        sizes = [fold.test.row_count for fold in folds]
        assert max(sizes) - min(sizes) <= 1

    async def test_folds_partition_rows_and_train_is_the_complement(self) -> None:
        labels = [0, 1] * 15
        folds = await _Fixtures.knot().process(
            dataset=_Fixtures.dataset(labels), stratify_column="y", k=5
        )
        test_rows = sorted(row for fold in folds for row in fold.test.row_indices)
        assert test_rows == list(range(30))
        for fold in folds:
            assert set(fold.train.row_indices) == set(range(30)) - set(fold.test.row_indices)

    async def test_stratifies_on_a_feature_column(self) -> None:
        labels = [1] * 6 + [0] * 24
        folds = await _Fixtures.knot().process(
            dataset=_Fixtures.dataset(labels), stratify_column="label_copy", k=3
        )
        for fold in folds:
            assert Counter(labels[row] for row in fold.test.row_indices)[1] == 2

    async def test_same_seed_same_folds_different_seed_different_folds(self) -> None:
        dataset = _Fixtures.dataset([0, 1] * 20)
        first = await _Fixtures.knot().process(dataset=dataset, stratify_column="y", k=4)
        again = await _Fixtures.knot().process(dataset=dataset, stratify_column="y", k=4)
        other = await _Fixtures.knot().process(
            dataset=dataset, stratify_column="y", k=4, random_seed=99
        )
        rows = [fold.test.row_indices for fold in first]
        assert rows == [fold.test.row_indices for fold in again]
        assert rows != [fold.test.row_indices for fold in other]


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_class_smaller_than_k(self) -> None:
        with pytest.raises(ValueError, match="every class needs at least k=4"):
            await _Fixtures.knot().process(
                dataset=_Fixtures.dataset([1] * 3 + [0] * 20), stratify_column="y", k=4
            )

    async def test_rejects_unknown_column(self) -> None:
        with pytest.raises(ValueError, match="neither the target"):
            await _Fixtures.knot().process(
                dataset=_Fixtures.dataset([0, 1] * 5), stratify_column="nope", k=2
            )

    async def test_rejects_manifest_only_dataset(self) -> None:
        with pytest.raises(TypeError, match="DatasetPayload"):
            await _Fixtures.knot().process(
                dataset=DatasetManifest(name="d", row_count=10),
                stratify_column="y",
                k=2,
            )

    async def test_rejects_k_below_two(self) -> None:
        with pytest.raises(ValueError, match="k must be >= 2"):
            await _Fixtures.knot().process(
                dataset=_Fixtures.dataset([0, 1] * 5), stratify_column="y", k=1
            )
