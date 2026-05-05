"""Unit tests for :class:`InteractionFeatureGenerator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.interaction_feature_generator import (
    InteractionFeatureGenerator,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


class _SplitSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DataSplit:
        ds = MLDataset(name="ds", feature_names=("a", "b"), row_count=10)
        return DataSplit(train=ds, test=ds)


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_column_pairs(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                InteractionFeatureGenerator(
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    column_pairs=[],
                    _config=KnotConfig(id="ifg"),
                )

    def test_rejects_invalid_pair_format(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                InteractionFeatureGenerator(
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    column_pairs=[("a",)],  # type: ignore[list-item]
                    _config=KnotConfig(id="ifg"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_interaction_features(self) -> None:
        with Tapestry() as t:
            src = _SplitSource(_config=KnotConfig(id="src"))
            InteractionFeatureGenerator(
                split=src,
                column_pairs=[("a", "b")],
                _config=KnotConfig(id="ifg"),
            )
        result = await t.run(RunRequest())
        split = result.outputs["ifg"]
        self.assertIsInstance(split, DataSplit)
        self.assertIn("a_x_b", split.train.feature_names)
