"""Tests for :class:`HyperbandTuner`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.experiments.hyperband_tuner import (
    HyperbandTuner,
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
    def test_rejects_max_configs_below_one(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaisesRegex(ValueError, "max_configs must be >= 1"):
                HyperbandTuner(
                    split=split,
                    algorithm="rf",
                    search_space={"n": (1, 2)},
                    primary_metric="accuracy",
                    max_configs=0,
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_primary_metric(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaisesRegex(ValueError, "primary_metric"):
                HyperbandTuner(
                    split=split,
                    algorithm="rf",
                    search_space={"n": (1, 2)},
                    primary_metric="",
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_best_model_eval_report_and_rounds(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            HyperbandTuner(
                split=split,
                algorithm="rf",
                search_space={"n_estimators": (10, 20, 30)},
                primary_metric="accuracy",
                max_configs=8,
                _config=KnotConfig(id="hb"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["hb"]
        assert isinstance(out, dict)
        assert isinstance(out["best_model"], TrainedModel)
        assert isinstance(out["eval_report"], EvalReport)
        assert isinstance(out["rounds"], int)
        assert out["rounds"] >= 1

    def test_rounds_property(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            tuner = HyperbandTuner(
                split=split,
                algorithm="rf",
                search_space={"n": (1,)},
                primary_metric="acc",
                max_configs=16,
                _config=KnotConfig(id="hb"),
            )
        assert tuner.rounds == 4
