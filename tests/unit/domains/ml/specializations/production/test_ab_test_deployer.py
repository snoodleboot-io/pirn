"""Tests for :class:`ABTestDeployer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.ab_test_deployer import (
    ABTestDeployer,
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
    return TrainedModel(model_id="model-a", algorithm="logistic", feature_names=("a",))


@knot
async def emit_model_b() -> TrainedModel:
    return TrainedModel(model_id="model-b", algorithm="svm", feature_names=("a",))


class TestConstruction:
    def test_rejects_non_knot_model_a(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            model_b = emit_model_b(_config=KnotConfig(id="mb"))
            with pytest.raises(TypeError, match="model_a must be a Knot"):
                ABTestDeployer(
                    model_a="bad",  # type: ignore[arg-type]
                    model_b=model_b,
                    split=split,
                    primary_metric="accuracy",
                    _config=KnotConfig(id="bad"),
                )


@pytest.mark.asyncio
class TestHappyPath:
    async def test_returns_winner_and_significance(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model_a = emit_model_a(_config=KnotConfig(id="ma"))
            model_b = emit_model_b(_config=KnotConfig(id="mb"))
            ABTestDeployer(
                model_a=model_a,
                model_b=model_b,
                split=split,
                primary_metric="accuracy",
                _config=KnotConfig(id="ab"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["ab"]
        assert out["winner"] in ("a", "b", "tie")
        assert isinstance(out["significant"], bool)
        assert 0.0 <= out["p_value"] <= 1.0
        assert out["primary_metric"] == "accuracy"
