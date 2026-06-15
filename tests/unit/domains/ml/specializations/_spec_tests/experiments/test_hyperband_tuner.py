"""Tests for :class:`HyperbandTuner`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.experiments.hyperband_tuner import (
    HyperbandTuner,
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


def _make_tuner() -> HyperbandTuner:
    with Tapestry():
        split = emit_split(_config=KnotConfig(id="split"))
        tuner = HyperbandTuner(
            split=split,
            algorithm="rf",
            search_space={"n": (1, 2)},
            primary_metric="accuracy",
            max_configs=8,
            _config=KnotConfig(id="hb"),
        )
    return tuner


def _split_fixture() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_max_configs_below_one(self) -> None:
        tuner = _make_tuner()
        split = _split_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await tuner.process(
                split=split,
                algorithm="rf",
                search_space={"n": (1, 2)},
                primary_metric="accuracy",
                max_configs=0,
            )

    async def test_rejects_empty_primary_metric(self) -> None:
        tuner = _make_tuner()
        split = _split_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await tuner.process(
                split=split,
                algorithm="rf",
                search_space={"n": (1, 2)},
                primary_metric="",
                max_configs=8,
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
        assert isinstance(out["best_model"], ModelManifest)
        assert isinstance(out["eval_report"], EvalReportPayload)
        assert isinstance(out["rounds"], int)
        assert out["rounds"] >= 1

