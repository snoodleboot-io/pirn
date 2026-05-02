"""Tests for :class:`TrainTestSplit`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.data_prep.train_test_split import TrainTestSplit
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_dataset() -> MLDataset:
    return MLDataset(
        name="customers",
        feature_names=("a", "b"),
        target_name="y",
        row_count=1000,
        source_uri="db://x",
    )


class TestTrainTestSplitHappyPath:
    async def test_emits_three_partitions(self) -> None:
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            TrainTestSplit(
                dataset=dataset,
                test_fraction=0.2,
                validation_fraction=0.1,
                random_seed=7,
                _config=KnotConfig(id="split"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out: DataSplit = result.outputs["split"]
        assert isinstance(out, DataSplit)
        assert out.validation is not None
        total = out.train.row_count + out.validation.row_count + out.test.row_count
        assert total == 1000
        assert out.train.feature_names == ("a", "b")
        assert out.test.target_name == "y"


class TestTrainTestSplitConstruction:
    def test_rejects_test_fraction_at_one(self) -> None:
        with Tapestry():
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            with pytest.raises(ValueError, match="test_fraction"):
                TrainTestSplit(
                    dataset=dataset,
                    test_fraction=1.0,
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_combined_fractions_at_one(self) -> None:
        with Tapestry():
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            with pytest.raises(ValueError, match="must be < 1"):
                TrainTestSplit(
                    dataset=dataset,
                    test_fraction=0.6,
                    validation_fraction=0.5,
                    _config=KnotConfig(id="bad"),
                )
