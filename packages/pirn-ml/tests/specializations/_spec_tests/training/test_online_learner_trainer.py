"""Tests for :class:`OnlineLearnerTrainer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.training.online_learner_trainer import (
    OnlineLearnerTrainer,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=100)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_n_batches_below_one(self) -> None:
        with Tapestry():
            k = OnlineLearnerTrainer.__new__(OnlineLearnerTrainer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = SplitManifest(
            train=DatasetManifest(name="d:train", feature_names=("a",), row_count=100),
            test=DatasetManifest(name="d:test", feature_names=("a",), row_count=20),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, algorithm="sgd", monitor_metric="accuracy", n_batches=0)

    async def test_rejects_empty_monitor_metric(self) -> None:
        with Tapestry():
            k = OnlineLearnerTrainer.__new__(OnlineLearnerTrainer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = SplitManifest(
            train=DatasetManifest(name="d:train", feature_names=("a",), row_count=100),
            test=DatasetManifest(name="d:test", feature_names=("a",), row_count=20),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, algorithm="sgd", monitor_metric="")


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_model_report_and_batch_count(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            OnlineLearnerTrainer(
                split=split,
                algorithm="sgd",
                monitor_metric="accuracy",
                n_batches=5,
                _config=KnotConfig(id="ol"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["ol"]
        assert isinstance(out, dict)
        assert isinstance(out["model"], ModelManifest)
        assert isinstance(out["eval_report"], EvalReportPayload)
        assert out["n_batches"] == 5
