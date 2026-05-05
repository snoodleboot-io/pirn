"""Tests for :class:`StackingEnsembleBuilder`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.training.stacking_ensemble_builder import (
    StackingEnsembleBuilder,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
    return DataSplit(train=train, test=test)


class TestConstruction(unittest.TestCase):
    def test_rejects_fewer_than_two_base_algorithms(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaisesRegex(ValueError, "at least two"):
                StackingEnsembleBuilder(
                    split=split,
                    base_algorithms=("rf",),
                    meta_algorithm="lr",
                    metrics=("accuracy",),
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_meta_algorithm(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaisesRegex(ValueError, "meta_algorithm"):
                StackingEnsembleBuilder(
                    split=split,
                    base_algorithms=("rf", "dt"),
                    meta_algorithm="",
                    metrics=("accuracy",),
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_stacked_ensemble_and_report(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            StackingEnsembleBuilder(
                split=split,
                base_algorithms=("rf", "dt"),
                meta_algorithm="lr",
                metrics=("accuracy",),
                _config=KnotConfig(id="stk"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["stk"]
        assert isinstance(out, dict)
        assert isinstance(out["ensemble_model"], TrainedModel)
        assert isinstance(out["eval_report"], EvalReport)
        assert out["n_base_models"] == 2
