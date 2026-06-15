"""Tests for :class:`GridSearchTuner`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.experiments.grid_search_tuner import (
    GridSearchTuner,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


def _make_tuner() -> GridSearchTuner:
    with Tapestry():
        split = emit_split(_config=KnotConfig(id="split"))
        tuner = GridSearchTuner(
            split=split,
            algorithm="rf",
            search_space={"n": (1, 2)},
            primary_metric="accuracy",
            _config=KnotConfig(id="grid"),
        )
    return tuner


def _split_fixture() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_search_space(self) -> None:
        tuner = _make_tuner()
        split = _split_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await tuner.process(
                split=split,
                algorithm="rf",
                search_space={},
                primary_metric="accuracy",
            )

    async def test_rejects_empty_algorithm(self) -> None:
        tuner = _make_tuner()
        split = _split_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await tuner.process(
                split=split,
                algorithm="",
                search_space={"n": (1, 2)},
                primary_metric="accuracy",
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_best_model_and_eval_report(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            GridSearchTuner(
                split=split,
                algorithm="rf",
                search_space={"n_estimators": (10, 20), "max_depth": (3, 5)},
                primary_metric="accuracy",
                _config=KnotConfig(id="grid"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["grid"]
        assert isinstance(out, dict)
        assert isinstance(out["best_model"], ModelManifest)
        assert out["best_model"].algorithm == "rf"
        assert isinstance(out["eval_report"], EvalReportPayload)
        assert "accuracy" in out["eval_report"].metrics.scores
