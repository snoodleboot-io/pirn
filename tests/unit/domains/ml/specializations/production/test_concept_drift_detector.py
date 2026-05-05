"""Tests for :class:`ConceptDriftDetector`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.concept_drift_detector import (
    ConceptDriftDetector,
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
async def emit_model() -> TrainedModel:
    return TrainedModel(model_id="m1", algorithm="logistic")


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_method(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            with self.assertRaisesRegex(ValueError, "method"):
                ConceptDriftDetector(
                    model=model,
                    split=split,
                    method="eddm",
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_nonpositive_delta(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            with self.assertRaisesRegex(ValueError, "delta"):
                ConceptDriftDetector(
                    model=model,
                    split=split,
                    delta=0.0,
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_concept_drift_result(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            ConceptDriftDetector(
                model=model,
                split=split,
                method="adwin",
                _config=KnotConfig(id="cd"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["cd"]
        assert isinstance(out["drift_detected"], bool)
        assert 0.0 <= out["statistic"] <= 1.0
        assert out["method"] == "adwin"
