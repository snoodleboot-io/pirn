"""Tests for :class:`EarlyStoppingTrainer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.training.early_stopping_trainer import (
    EarlyStoppingTrainer,
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
    async def test_rejects_patience_below_one(self) -> None:
        with Tapestry():
            k = EarlyStoppingTrainer.__new__(EarlyStoppingTrainer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = SplitManifest(
            train=DatasetManifest(name="d:train", feature_names=("a",), row_count=80),
            test=DatasetManifest(name="d:test", feature_names=("a",), row_count=20),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, algorithm="nn", monitor_metric="val_loss", patience=0)

    async def test_rejects_empty_monitor_metric(self) -> None:
        with Tapestry():
            k = EarlyStoppingTrainer.__new__(EarlyStoppingTrainer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = SplitManifest(
            train=DatasetManifest(name="d:train", feature_names=("a",), row_count=80),
            test=DatasetManifest(name="d:test", feature_names=("a",), row_count=20),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, algorithm="nn", monitor_metric="")

    async def test_rejects_max_epochs_below_one(self) -> None:
        with Tapestry():
            k = EarlyStoppingTrainer.__new__(EarlyStoppingTrainer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = SplitManifest(
            train=DatasetManifest(name="d:train", feature_names=("a",), row_count=80),
            test=DatasetManifest(name="d:test", feature_names=("a",), row_count=20),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, algorithm="nn", monitor_metric="val_loss", max_epochs=0)


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_model_report_and_metadata(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            EarlyStoppingTrainer(
                split=split,
                algorithm="nn",
                monitor_metric="val_loss",
                patience=3,
                max_epochs=50,
                _config=KnotConfig(id="est"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["est"]
        assert isinstance(out, dict)
        assert isinstance(out["model"], ModelManifest)
        assert isinstance(out["eval_report"], EvalReportPayload)
        assert out["patience"] == 3
        assert out["stopped_epoch"] == 50
