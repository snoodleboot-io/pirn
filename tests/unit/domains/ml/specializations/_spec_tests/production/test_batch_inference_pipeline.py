"""Tests for :class:`BatchInferencePipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.batch_inference_pipeline import (
    BatchInferencePipeline,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


@knot
async def emit_model() -> ModelManifest:
    return ModelManifest(
        model_id="m1",
        algorithm="rf",
        feature_names=("a",),
        target_name="y",
    )


def _fixtures():
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    split = SplitManifest(train=train, test=test)
    model = ModelManifest(
        model_id="m1", algorithm="rf", feature_names=("a",), target_name="y"
    )
    return model, split


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_zero_batch_size(self) -> None:
        with Tapestry():
            k = BatchInferencePipeline.__new__(BatchInferencePipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, batch_size=0)

    async def test_rejects_empty_output_column(self) -> None:
        with Tapestry():
            k = BatchInferencePipeline.__new__(BatchInferencePipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, batch_size=128, output_column="")


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_prediction_summary(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            BatchInferencePipeline(
                model=model,
                split=split,
                batch_size=10,
                output_column="score",
                _config=KnotConfig(id="bip"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["bip"]
        assert "rows_processed" in out
        assert "batches" in out
        assert out["output_column"] == "score"
