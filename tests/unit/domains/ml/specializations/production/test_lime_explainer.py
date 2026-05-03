"""Tests for :class:`LIMEExplainer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.lime_explainer import (
    LIMEExplainer,
)
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
        model_id="m1", algorithm="logistic", feature_names=("a", "b")
    )


class TestConstruction:
    def test_rejects_zero_n_samples(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            with pytest.raises(ValueError, match="n_samples"):
                LIMEExplainer(
                    model=model,
                    split=split,
                    n_samples=0,
                    _config=KnotConfig(id="bad"),
                )


@pytest.mark.asyncio
class TestHappyPath:
    async def test_emits_feature_importance(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            LIMEExplainer(
                model=model,
                split=split,
                n_samples=50,
                _config=KnotConfig(id="lime"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["lime"]
        assert set(out["feature_importance"].keys()) == {"a", "b"}
        assert out["n_samples"] == 50
        assert out["n_explained"] == 20
