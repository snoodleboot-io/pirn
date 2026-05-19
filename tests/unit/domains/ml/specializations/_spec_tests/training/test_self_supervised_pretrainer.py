"""Tests for :class:`SelfSupervisedPretrainer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.training.self_supervised_pretrainer import (
    SelfSupervisedPretrainer,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("x",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("x",), row_count=20)
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_pretrain_algorithm(self) -> None:
        with Tapestry():
            k = SelfSupervisedPretrainer.__new__(SelfSupervisedPretrainer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = SplitManifest(
            train=DatasetManifest(name="d:train", feature_names=("x",), row_count=80),
            test=DatasetManifest(name="d:test", feature_names=("x",), row_count=20),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, pretrain_algorithm="", finetune_algorithm="lr", metrics=("accuracy",))

    async def test_rejects_empty_finetune_algorithm(self) -> None:
        with Tapestry():
            k = SelfSupervisedPretrainer.__new__(SelfSupervisedPretrainer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = SplitManifest(
            train=DatasetManifest(name="d:train", feature_names=("x",), row_count=80),
            test=DatasetManifest(name="d:test", feature_names=("x",), row_count=20),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, pretrain_algorithm="mae", finetune_algorithm="", metrics=("accuracy",))

    async def test_rejects_empty_metrics(self) -> None:
        with Tapestry():
            k = SelfSupervisedPretrainer.__new__(SelfSupervisedPretrainer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = SplitManifest(
            train=DatasetManifest(name="d:train", feature_names=("x",), row_count=80),
            test=DatasetManifest(name="d:test", feature_names=("x",), row_count=20),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, pretrain_algorithm="mae", finetune_algorithm="lr", metrics=())


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_model_report_and_algorithm_info(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            SelfSupervisedPretrainer(
                split=split,
                pretrain_algorithm="masked_ae",
                finetune_algorithm="lr",
                metrics=("accuracy",),
                _config=KnotConfig(id="ssp"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["ssp"]
        assert isinstance(out, dict)
        assert isinstance(out["model"], ModelManifest)
        assert isinstance(out["eval_report"], EvalReportPayload)
        assert out["pretrain_algorithm"] == "masked_ae"
        assert out["finetune_algorithm"] == "lr"
