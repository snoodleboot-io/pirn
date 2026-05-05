"""Tests for :class:`InteractionFeatureGenerator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.interaction_feature_generator import (
    InteractionFeatureGenerator,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(
        name="d:train",
        feature_names=("age", "income"),
        target_name="y",
        row_count=80,
    )
    test = MLDataset(
        name="d:test",
        feature_names=("age", "income"),
        target_name="y",
        row_count=20,
    )
    return DataSplit(train=train, test=test)


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_column_pairs(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaisesRegex(ValueError, "column_pairs must be non-empty"):
                InteractionFeatureGenerator(
                    split=split,
                    column_pairs=[],
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_malformed_pair(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaisesRegex(ValueError, "non-empty strings"):
                InteractionFeatureGenerator(
                    split=split,
                    column_pairs=[("age",)],  # type: ignore[list-item]
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_appends_interaction_feature_names(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            InteractionFeatureGenerator(
                split=split,
                column_pairs=[("age", "income")],
                _config=KnotConfig(id="ifg"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["ifg"]
        assert isinstance(out, DataSplit)
        features = out.train.feature_names
        assert "age_x_income" in features
        assert "age" in features
        assert "income" in features
        assert "interactions" in out.train.name
