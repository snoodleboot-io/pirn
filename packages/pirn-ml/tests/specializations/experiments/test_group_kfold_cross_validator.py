"""Unit tests for :class:`GroupKFoldCrossValidator`."""

from __future__ import annotations

import unittest
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_ml.specializations.experiments.group_kfold_cross_validator import (
    GroupKFoldCrossValidator,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.dataset_payload import DatasetPayload
from pirn_ml.types.ml_features import MLFeatures


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


def _payload() -> DatasetPayload:
    return DatasetPayload(
        metadata=DatasetManifest(
            name="ds", feature_names=("patient_id",), target_name="y", row_count=10
        ),
        data=MLFeatures(
            feature_matrix=np.arange(10, dtype=float).reshape(10, 1), target_vector=np.zeros(10)
        ),
    )


class TestConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            GroupKFoldCrossValidator(
                dataset=_KnotStub(_config=KnotConfig(id="d")),
                algorithm="rf",
                metrics=["accuracy"],
                group_column="patient_id",
                k=5,
                _config=KnotConfig(id="gkf"),
            )
        self.assertIsNotNone(t._store.get("gkf"))


class TestProcessValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> GroupKFoldCrossValidator:
        with Tapestry():
            return GroupKFoldCrossValidator(
                dataset=_KnotStub(_config=KnotConfig(id="d")),
                algorithm="rf",
                metrics=["accuracy"],
                group_column="patient_id",
                k=5,
                _config=KnotConfig(id="gkf"),
            )

    async def test_rejects_k_less_than_2(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                dataset=_payload(),
                algorithm="rf",
                metrics=["accuracy"],
                group_column="patient_id",
                k=1,
            )

    async def test_rejects_empty_group_column(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                dataset=_payload(),
                algorithm="rf",
                metrics=["accuracy"],
                group_column="",
                k=5,
            )


class TestRejectsManifestOnlyDataset(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_dataset_without_rows(self) -> None:
        with Tapestry():
            knot = GroupKFoldCrossValidator(
                dataset=_KnotStub(_config=KnotConfig(id="d")),
                algorithm="rf",
                metrics=["accuracy"],
                group_column="patient_id",
                k=2,
                _config=KnotConfig(id="gkf"),
            )
        with self.assertRaises(TypeError):
            await knot.process(
                dataset=_payload().metadata,
                algorithm="rf",
                metrics=["accuracy"],
                group_column="patient_id",
                k=2,
            )
