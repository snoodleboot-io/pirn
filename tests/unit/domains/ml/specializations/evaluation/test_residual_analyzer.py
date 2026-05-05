"""Tests for :class:`ResidualAnalyzer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.residual_analyzer import (
    ResidualAnalyzer,
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
    return TrainedModel(model_id="m1", algorithm="linear", feature_names=("a",))


class TestConstruction(unittest.TestCase):
    def test_rejects_n_bins_less_than_two(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            with self.assertRaisesRegex(ValueError, "n_bins"):
                ResidualAnalyzer(
                    model=model,
                    split=split,
                    n_bins=1,
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_residual_diagnostics(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            ResidualAnalyzer(
                model=model,
                split=split,
                n_bins=10,
                _config=KnotConfig(id="res"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["res"]
        assert len(out["histogram"]) == 10
        assert len(out["qq_theoretical"]) == 10
        assert 0.0 <= out["durbin_watson"] <= 4.0
        assert isinstance(out["heteroscedastic"], bool)
