"""Tests for :class:`FineTuningTrainer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.training.fine_tuning_trainer import (
    FineTuningTrainer,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("x",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("x",), row_count=20)
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_pretrained_model_id(self) -> None:
        with Tapestry():
            k = FineTuningTrainer.__new__(FineTuningTrainer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = SplitManifest(
            train=DatasetManifest(name="d:train", feature_names=("x",), row_count=80),
            test=DatasetManifest(name="d:test", feature_names=("x",), row_count=20),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, pretrained_model_id="", algorithm="nn", metrics=("accuracy",))

    async def test_rejects_negative_frozen_layers(self) -> None:
        with Tapestry():
            k = FineTuningTrainer.__new__(FineTuningTrainer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = SplitManifest(
            train=DatasetManifest(name="d:train", feature_names=("x",), row_count=80),
            test=DatasetManifest(name="d:test", feature_names=("x",), row_count=20),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, pretrained_model_id="bert-base", algorithm="nn", metrics=("accuracy",), frozen_layers=-1)


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_model_report_and_pretrain_info(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            FineTuningTrainer(
                split=split,
                pretrained_model_id="bert-base",
                algorithm="nn",
                metrics=("accuracy",),
                frozen_layers=6,
                _config=KnotConfig(id="ft"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["ft"]
        assert isinstance(out, dict)
        assert isinstance(out["model"], ModelManifest)
        assert isinstance(out["eval_report"], EvalReportPayload)
        assert out["pretrained_model_id"] == "bert-base"
        assert out["frozen_layers"] == 6
