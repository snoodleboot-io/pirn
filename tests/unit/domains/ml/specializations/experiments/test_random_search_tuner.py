"""Unit tests for :class:`RandomSearchTuner`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.experiments.random_search_tuner import (
    RandomSearchTuner,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


def _make_tuner() -> RandomSearchTuner:
    with Tapestry():
        stub = _KnotStub(_config=KnotConfig(id="s"))
        return RandomSearchTuner(
            split=stub,
            algorithm="xgboost",
            search_space={"lr": [0.01, 0.1]},
            primary_metric="accuracy",
            n_trials=10,
            _config=KnotConfig(id="rs"),
        )


class TestConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            RandomSearchTuner(
                split=_KnotStub(_config=KnotConfig(id="s")),
                algorithm="xgboost",
                search_space={"lr": [0.01, 0.1]},
                primary_metric="accuracy",
                n_trials=10,
                _config=KnotConfig(id="rs"),
            )
        self.assertIsNotNone(t._store.get("rs"))


class TestProcessValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_search_space(self) -> None:
        tuner = _make_tuner()
        from pirn.domains.ml.types.data_split import DataSplit
        from pirn.domains.ml.types.ml_dataset import MLDataset

        ds = MLDataset(
            name="ds",
            feature_names=("x",),
            target_name="y",
            row_count=10,
            source_uri="memory://ds",
        )
        split = DataSplit(
            train=ds,
            test=ds,
        )
        with self.assertRaises(ValueError):
            await tuner.process(
                split=split,
                algorithm="xgboost",
                search_space={},
                primary_metric="accuracy",
            )

    async def test_rejects_n_trials_less_than_1(self) -> None:
        tuner = _make_tuner()
        from pirn.domains.ml.types.data_split import DataSplit
        from pirn.domains.ml.types.ml_dataset import MLDataset

        ds = MLDataset(
            name="ds",
            feature_names=("x",),
            target_name="y",
            row_count=10,
            source_uri="memory://ds",
        )
        split = DataSplit(
            train=ds,
            test=ds,
        )
        with self.assertRaises(ValueError):
            await tuner.process(
                split=split,
                algorithm="xgboost",
                search_space={"lr": [0.01]},
                primary_metric="accuracy",
                n_trials=0,
            )

    async def test_rejects_empty_algorithm(self) -> None:
        tuner = _make_tuner()
        from pirn.domains.ml.types.data_split import DataSplit
        from pirn.domains.ml.types.ml_dataset import MLDataset

        ds = MLDataset(
            name="ds",
            feature_names=("x",),
            target_name="y",
            row_count=10,
            source_uri="memory://ds",
        )
        split = DataSplit(
            train=ds,
            test=ds,
        )
        with self.assertRaises(ValueError):
            await tuner.process(
                split=split,
                algorithm="",
                search_space={"lr": [0.01]},
                primary_metric="accuracy",
            )

    async def test_rejects_empty_primary_metric(self) -> None:
        tuner = _make_tuner()
        from pirn.domains.ml.types.data_split import DataSplit
        from pirn.domains.ml.types.ml_dataset import MLDataset

        ds = MLDataset(
            name="ds",
            feature_names=("x",),
            target_name="y",
            row_count=10,
            source_uri="memory://ds",
        )
        split = DataSplit(
            train=ds,
            test=ds,
        )
        with self.assertRaises(ValueError):
            await tuner.process(
                split=split,
                algorithm="xgboost",
                search_space={"lr": [0.01]},
                primary_metric="",
            )
