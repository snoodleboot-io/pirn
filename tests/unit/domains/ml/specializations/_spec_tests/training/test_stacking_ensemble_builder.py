"""Tests for :class:`StackingEnsembleBuilder`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.training.stacking_ensemble_builder import (
    StackingEnsembleBuilder,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_fewer_than_two_base_algorithms(self) -> None:
        with Tapestry():
            k = StackingEnsembleBuilder.__new__(StackingEnsembleBuilder)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = SplitManifest(
            train=DatasetManifest(name="d:train", feature_names=("a",), row_count=80),
            test=DatasetManifest(name="d:test", feature_names=("a",), row_count=20),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, base_algorithms=("rf",), meta_algorithm="lr", metrics=("accuracy",))

    async def test_rejects_empty_meta_algorithm(self) -> None:
        with Tapestry():
            k = StackingEnsembleBuilder.__new__(StackingEnsembleBuilder)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = SplitManifest(
            train=DatasetManifest(name="d:train", feature_names=("a",), row_count=80),
            test=DatasetManifest(name="d:test", feature_names=("a",), row_count=20),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, base_algorithms=("rf", "dt"), meta_algorithm="", metrics=("accuracy",))


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
        assert isinstance(out["ensemble_model"], ModelManifest)
        assert isinstance(out["eval_report"], EvalReportPayload)
        assert out["n_base_models"] == 2
