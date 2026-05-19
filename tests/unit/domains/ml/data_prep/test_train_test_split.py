"""Tests for :class:`TrainTestSplit`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.data_prep.train_test_split import TrainTestSplit
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.tapestry import Tapestry


@knot
async def emit_dataset() -> DatasetManifest:
    return DatasetManifest(
        name="customers",
        feature_names=("a", "b"),
        target_name="y",
        row_count=1000,
        source_uri="db://x",
    )


def _make_dataset(row_count: int = 1000) -> DatasetManifest:
    return DatasetManifest(
        name="customers",
        feature_names=("a", "b"),
        target_name="y",
        row_count=row_count,
        source_uri="db://x",
    )


class TestTrainTestSplitHappyPath(unittest.IsolatedAsyncioTestCase):
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
        out: SplitManifest = result.outputs["split"]
        assert isinstance(out, SplitManifest)
        assert out.validation is not None
        total = out.train.row_count + out.validation.row_count + out.test.row_count
        assert total == 1000
        assert out.train.feature_names == ("a", "b")
        assert out.test.target_name == "y"


class TestTrainTestSplitProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> TrainTestSplit:
        with Tapestry():
            tts = TrainTestSplit.__new__(TrainTestSplit)
            object.__setattr__(tts, "_config", KnotConfig(id="x"))
        return tts

    async def test_rejects_test_fraction_at_one(self) -> None:
        tts = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await tts.process(dataset=_make_dataset(), test_fraction=1.0)

    async def test_rejects_combined_fractions_at_one(self) -> None:
        tts = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await tts.process(
                dataset=_make_dataset(),
                test_fraction=0.6,
                validation_fraction=0.5,
            )
