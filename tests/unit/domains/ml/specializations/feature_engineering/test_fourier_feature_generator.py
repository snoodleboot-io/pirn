"""Unit tests for :class:`FourierFeatureGenerator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.fourier_feature_generator import (
    FourierFeatureGenerator,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


class _SplitSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DataSplit:
        ds = MLDataset(name="ds", feature_names=("hour",), row_count=100)
        return DataSplit(train=ds, test=ds)


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_columns(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                FourierFeatureGenerator(
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    columns=[],
                    periods=[24],
                    _config=KnotConfig(id="ffg"),
                )

    def test_rejects_period_less_than_2(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                FourierFeatureGenerator(
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    columns=["hour"],
                    periods=[1],
                    _config=KnotConfig(id="ffg"),
                )

    def test_rejects_non_int_period(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                FourierFeatureGenerator(
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    columns=["hour"],
                    periods=[24.0],  # type: ignore[list-item]
                    _config=KnotConfig(id="ffg"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_sin_cos_features(self) -> None:
        with Tapestry() as t:
            src = _SplitSource(_config=KnotConfig(id="src"))
            FourierFeatureGenerator(
                split=src,
                columns=["hour"],
                periods=[24],
                _config=KnotConfig(id="ffg"),
            )
        result = await t.run(RunRequest())
        split = result.outputs["ffg"]
        self.assertIsInstance(split, DataSplit)
        self.assertIn("hour_sin_24", split.train.feature_names)
        self.assertIn("hour_cos_24", split.train.feature_names)
