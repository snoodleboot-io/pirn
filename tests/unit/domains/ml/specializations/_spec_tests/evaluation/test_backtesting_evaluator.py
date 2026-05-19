"""Tests for :class:`BacktestingEvaluator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.backtesting_evaluator import (
    BacktestingEvaluator,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.model_manifest import ModelManifest
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
        algorithm="arima",
        feature_names=("a",),
        target_name="y",
    )


def _fixtures():
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    split = SplitManifest(train=train, test=test)
    model = ModelManifest(
        model_id="m1", algorithm="arima", feature_names=("a",), target_name="y"
    )
    return model, split


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_zero_windows(self) -> None:
        with Tapestry():
            k = BacktestingEvaluator.__new__(BacktestingEvaluator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, n_windows=0)

    async def test_rejects_empty_metric(self) -> None:
        with Tapestry():
            k = BacktestingEvaluator.__new__(BacktestingEvaluator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, n_windows=3, metric="")


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_window_scores(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            BacktestingEvaluator(
                model=model,
                split=split,
                n_windows=3,
                metric="mape",
                _config=KnotConfig(id="bt"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["bt"]
        assert "window_scores" in out
        assert len(out["window_scores"]) == 3
        assert "mean_score" in out
