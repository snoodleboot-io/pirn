"""Tests for :class:`GroupCrossValidator` — groups never straddle train and test."""

from __future__ import annotations

import unittest

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_ml.data_prep.group_cross_validator import GroupCrossValidator
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.dataset_payload import DatasetPayload
from pirn_ml.types.ml_features import MLFeatures


class _Fixtures:
    @staticmethod
    def dataset(groups: list[int]) -> DatasetPayload:
        rows = len(groups)
        features = np.column_stack([np.arange(rows, dtype=float), np.array(groups, dtype=float)])
        return DatasetPayload(
            metadata=DatasetManifest(
                name="visits",
                feature_names=("x", "patient_id"),
                target_name="y",
                row_count=rows,
            ),
            data=MLFeatures(feature_matrix=features, target_vector=np.zeros(rows)),
        )

    @staticmethod
    def knot() -> GroupCrossValidator:
        with Tapestry():
            knot = GroupCrossValidator.__new__(GroupCrossValidator)
            object.__setattr__(knot, "_config", KnotConfig(id="x"))
        return knot


class TestGrouping(unittest.IsolatedAsyncioTestCase):
    async def test_no_group_appears_in_both_train_and_test(self) -> None:
        # Interleaved groups: any row-position split would put a patient on both sides.
        groups = [row % 15 for row in range(60)]
        folds = await _Fixtures.knot().process(
            dataset=_Fixtures.dataset(groups), group_column="patient_id", k=4
        )
        assert len(folds) == 4
        for fold in folds:
            test_groups = {groups[row] for row in fold.test.row_indices}
            train_groups = {groups[row] for row in fold.train.row_indices}
            assert test_groups
            assert test_groups.isdisjoint(train_groups)

    async def test_each_group_is_tested_in_exactly_one_fold(self) -> None:
        groups = [row % 9 for row in range(45)]
        folds = await _Fixtures.knot().process(
            dataset=_Fixtures.dataset(groups), group_column="patient_id", k=3
        )
        homes: dict[int, set[int]] = {}
        for fold_index, fold in enumerate(folds):
            for row in fold.test.row_indices:
                homes.setdefault(groups[row], set()).add(fold_index)
        assert set(homes) == set(range(9))
        assert all(len(fold_indices) == 1 for fold_indices in homes.values())
        assert sorted(row for fold in folds for row in fold.test.row_indices) == list(range(45))

    async def test_unequal_groups_are_balanced_greedily(self) -> None:
        # group sizes 6, 5, 4, 3, 2 over k=2 -> [6, 3, 2] = 11 and [5, 4] = 9
        groups = [0] * 6 + [1] * 5 + [2] * 4 + [3] * 3 + [4] * 2
        folds = await _Fixtures.knot().process(
            dataset=_Fixtures.dataset(groups), group_column="patient_id", k=2
        )
        assert sorted(fold.test.row_count for fold in folds) == [9, 11]


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_fewer_groups_than_folds(self) -> None:
        with pytest.raises(ValueError, match="at least k=3 distinct groups"):
            await _Fixtures.knot().process(
                dataset=_Fixtures.dataset([0, 1] * 5), group_column="patient_id", k=3
            )

    async def test_rejects_unknown_column(self) -> None:
        with pytest.raises(ValueError, match="neither the target"):
            await _Fixtures.knot().process(
                dataset=_Fixtures.dataset([0, 1, 2] * 3), group_column="site", k=2
            )

    async def test_rejects_manifest_only_dataset(self) -> None:
        with pytest.raises(TypeError, match="DatasetPayload"):
            await _Fixtures.knot().process(
                dataset=DatasetManifest(name="d", row_count=10),
                group_column="patient_id",
                k=2,
            )
