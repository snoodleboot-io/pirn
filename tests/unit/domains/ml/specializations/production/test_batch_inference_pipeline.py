"""Tests for :class:`BatchInferencePipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.batch_inference_pipeline import (
    BatchInferencePipeline,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=100)
    return SplitManifest(train=train, test=test)


@knot
async def emit_model() -> ModelManifest:
    return ModelManifest(model_id="m1", algorithm="logistic", feature_names=("a",))


def _make_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=100)
    return SplitManifest(train=train, test=test)


def _make_model() -> ModelManifest:
    return ModelManifest(model_id="m1", algorithm="logistic", feature_names=("a",))


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_zero_batch_size(self) -> None:
        with Tapestry():
            k = BatchInferencePipeline.__new__(BatchInferencePipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                model=_make_model(),
                split=_make_split(),
                batch_size=0,
                output_column="prediction",
            )

    async def test_rejects_empty_output_column(self) -> None:
        with Tapestry():
            k = BatchInferencePipeline.__new__(BatchInferencePipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                model=_make_model(),
                split=_make_split(),
                batch_size=32,
                output_column="",
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_inference_summary(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            BatchInferencePipeline(
                model=model,
                split=split,
                batch_size=32,
                _config=KnotConfig(id="bi"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["bi"]
        assert out["rows_processed"] == 100
        assert out["batches"] == 4
        assert "prediction_hash" in out
