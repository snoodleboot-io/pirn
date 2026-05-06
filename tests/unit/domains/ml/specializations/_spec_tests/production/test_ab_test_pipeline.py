"""Tests for :class:`ABTestPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.ab_test_pipeline import (
    ABTestPipeline,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
    return DataSplit(train=train, test=test)


@knot
async def emit_model_a() -> TrainedModel:
    return TrainedModel(
        model_id="a", algorithm="logistic", feature_names=("a",), target_name="y"
    )


@knot
async def emit_model_b() -> TrainedModel:
    return TrainedModel(
        model_id="b", algorithm="rf", feature_names=("a",), target_name="y"
    )


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_string_metric(self) -> None:
        with Tapestry():
            k = ABTestPipeline.__new__(ABTestPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = DataSplit(
            train=MLDataset(name="tr", feature_names=("a",), row_count=80),
            test=MLDataset(name="te", feature_names=("a",), row_count=20),
        )
        model_a = TrainedModel(model_id="a", algorithm="logistic", feature_names=("a",), target_name="y")
        model_b = TrainedModel(model_id="b", algorithm="rf", feature_names=("a",), target_name="y")
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model_a=model_a, model_b=model_b, split=split, primary_metric="", alpha=0.05)

    async def test_rejects_alpha_outside_range(self) -> None:
        with Tapestry():
            k = ABTestPipeline.__new__(ABTestPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = DataSplit(
            train=MLDataset(name="tr", feature_names=("a",), row_count=80),
            test=MLDataset(name="te", feature_names=("a",), row_count=20),
        )
        model_a = TrainedModel(model_id="a", algorithm="logistic", feature_names=("a",), target_name="y")
        model_b = TrainedModel(model_id="b", algorithm="rf", feature_names=("a",), target_name="y")
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model_a=model_a, model_b=model_b, split=split, primary_metric="accuracy", alpha=1.5)


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_winner_and_p_value(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model_a = emit_model_a(_config=KnotConfig(id="ma"))
            model_b = emit_model_b(_config=KnotConfig(id="mb"))
            ABTestPipeline(
                model_a=model_a,
                model_b=model_b,
                split=split,
                primary_metric="accuracy",
                _config=KnotConfig(id="ab"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["ab"]
        assert out["winner"] in {"a", "b", "tie"}
        assert 0.0 <= out["p_value"] <= 1.0
        assert isinstance(out["effect_size"], float)
