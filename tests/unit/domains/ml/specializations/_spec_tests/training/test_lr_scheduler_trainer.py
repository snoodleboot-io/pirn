"""Tests for :class:`LRSchedulerTrainer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.training.lr_scheduler_trainer import (
    LRSchedulerTrainer,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_scheduler(self) -> None:
        with Tapestry():
            k = LRSchedulerTrainer.__new__(LRSchedulerTrainer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = SplitManifest(
            train=DatasetManifest(name="d:train", feature_names=("a",), row_count=80),
            test=DatasetManifest(name="d:test", feature_names=("a",), row_count=20),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, algorithm="nn", scheduler="exponential", metrics=("loss",))

    async def test_rejects_empty_metrics(self) -> None:
        with Tapestry():
            k = LRSchedulerTrainer.__new__(LRSchedulerTrainer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = SplitManifest(
            train=DatasetManifest(name="d:train", feature_names=("a",), row_count=80),
            test=DatasetManifest(name="d:test", feature_names=("a",), row_count=20),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, algorithm="nn", scheduler="cosine", metrics=())


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_model_report_and_scheduler(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            LRSchedulerTrainer(
                split=split,
                algorithm="nn",
                scheduler="cosine",
                metrics=("loss",),
                _config=KnotConfig(id="lrs"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["lrs"]
        assert isinstance(out, dict)
        assert isinstance(out["model"], ModelManifest)
        assert isinstance(out["eval_report"], EvalReportPayload)
        assert out["scheduler"] == "cosine"

    async def test_step_scheduler(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            LRSchedulerTrainer(
                split=split,
                algorithm="nn",
                scheduler="step",
                metrics=("accuracy",),
                _config=KnotConfig(id="lrs"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["lrs"]["scheduler"] == "step"
