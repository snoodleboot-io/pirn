"""Tests for :class:`TargetEncoder`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.target_encoder import (
    TargetEncoder,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(
        name="d:train", feature_names=("city",), target_name="y", row_count=80
    )
    test = MLDataset(
        name="d:test", feature_names=("city",), target_name="y", row_count=20
    )
    return DataSplit(train=train, test=test)


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_categorical_column(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaisesRegex(ValueError, "categorical_column"):
                TargetEncoder(
                    split=split,
                    categorical_column="",
                    target_column="y",
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_negative_smoothing(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaisesRegex(ValueError, "smoothing"):
                TargetEncoder(
                    split=split,
                    categorical_column="city",
                    target_column="y",
                    smoothing=-0.1,
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_target_encoded_split(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            TargetEncoder(
                split=split,
                categorical_column="city",
                target_column="y",
                smoothing=2.0,
                _config=KnotConfig(id="te"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["te"]
        assert isinstance(out, DataSplit)
        assert out.train.name.endswith("encoded_target")
