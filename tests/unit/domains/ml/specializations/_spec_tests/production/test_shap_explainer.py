"""Tests for :class:`SHAPExplainer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.shap_explainer import SHAPExplainer
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("a", "b"), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a", "b"), row_count=20)
    return DataSplit(train=train, test=test)


@knot
async def emit_model() -> TrainedModel:
    return TrainedModel(
        model_id="m1",
        algorithm="rf",
        feature_names=("a", "b"),
        target_name="y",
    )


def _fixtures():
    train = MLDataset(name="d:train", feature_names=("a", "b"), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a", "b"), row_count=20)
    split = DataSplit(train=train, test=test)
    model = TrainedModel(
        model_id="m1", algorithm="rf", feature_names=("a", "b"), target_name="y"
    )
    return model, split


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_valid_inputs(self) -> None:
        """SHAPExplainer.process() with valid inputs should not raise."""
        with Tapestry():
            k = SHAPExplainer.__new__(SHAPExplainer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model, split = _fixtures()
        result = await k.process(model=model, split=split)
        assert "feature_importance" in result
        assert "mean_abs_shap" in result


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_shap_values(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            SHAPExplainer(
                model=model,
                split=split,
                _config=KnotConfig(id="shap"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["shap"]
        assert "feature_importance" in out
        assert "mean_abs_shap" in out
        assert out["model_id"] == "m1"
