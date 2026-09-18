"""Unit tests for :class:`StratifiedKFoldValidator`."""

from __future__ import annotations

import unittest
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_ml.specializations.experiments.stratified_kfold_validator import (
    StratifiedKFoldValidator,
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
            name="ds", feature_names=("x",), target_name="y", row_count=10, source_uri="memory://ds"
        ),
        data=MLFeatures(feature_matrix=np.zeros((10, 1)), target_vector=np.array([0, 1] * 5)),
    )


def _make_validator() -> StratifiedKFoldValidator:
    with Tapestry():
        stub = _KnotStub(_config=KnotConfig(id="d"))
        return StratifiedKFoldValidator(
            dataset=stub,
            stratify_column="label",
            algorithm="rf",
            metrics=["accuracy"],
            k=5,
            _config=KnotConfig(id="skf"),
        )


class TestConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            StratifiedKFoldValidator(
                dataset=_KnotStub(_config=KnotConfig(id="d")),
                stratify_column="label",
                algorithm="rf",
                metrics=["accuracy"],
                k=5,
                _config=KnotConfig(id="skf"),
            )
        self.assertIsNotNone(t._store.get("skf"))


class TestProcessValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_k_less_than_2(self) -> None:
        validator = _make_validator()
        ds = _payload()
        with self.assertRaises(ValueError):
            await validator.process(
                dataset=ds,
                stratify_column="label",
                algorithm="rf",
                metrics=["accuracy"],
                k=1,
            )

    async def test_rejects_empty_stratify_column(self) -> None:
        validator = _make_validator()
        ds = _payload()
        with self.assertRaises(ValueError):
            await validator.process(
                dataset=ds,
                stratify_column="",
                algorithm="rf",
                metrics=["accuracy"],
                k=5,
            )

    async def test_rejects_empty_algorithm(self) -> None:
        validator = _make_validator()
        ds = _payload()
        with self.assertRaises(ValueError):
            await validator.process(
                dataset=ds,
                stratify_column="label",
                algorithm="",
                metrics=["accuracy"],
                k=5,
            )

    async def test_rejects_empty_metrics(self) -> None:
        validator = _make_validator()
        ds = _payload()
        with self.assertRaises(ValueError):
            await validator.process(
                dataset=ds,
                stratify_column="label",
                algorithm="rf",
                metrics=[],
                k=5,
            )


class TestRejectsManifestOnlyDataset(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_dataset_without_rows(self) -> None:
        validator = _make_validator()
        with self.assertRaises(TypeError):
            await validator.process(
                dataset=_payload().metadata,
                stratify_column="y",
                algorithm="rf",
                metrics=["accuracy"],
                k=2,
            )
