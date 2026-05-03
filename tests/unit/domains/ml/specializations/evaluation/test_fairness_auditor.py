"""Tests for :class:`FairnessAuditor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.fairness_auditor import (
    FairnessAuditor,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("a", "gender"), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a", "gender"), row_count=20)
    return DataSplit(train=train, test=test)


@knot
async def emit_model() -> TrainedModel:
    return TrainedModel(model_id="m1", algorithm="logistic", feature_names=("a",))


class TestConstruction:
    def test_rejects_empty_attributes(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            with pytest.raises(ValueError, match="protected_attributes"):
                FairnessAuditor(
                    model=model,
                    split=split,
                    protected_attributes=(),
                    _config=KnotConfig(id="bad"),
                )


@pytest.mark.asyncio
class TestHappyPath:
    async def test_emits_fairness_metrics(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            FairnessAuditor(
                model=model,
                split=split,
                protected_attributes=("gender", "age"),
                _config=KnotConfig(id="fair"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["fair"]
        assert "gender" in out["demographic_parity"]
        assert "age" in out["equalized_odds"]
        assert isinstance(out["individual_fairness"], float)
