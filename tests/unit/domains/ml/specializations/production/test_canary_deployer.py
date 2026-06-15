"""Tests for :class:`CanaryDeployer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.production.canary_deployer import (
    CanaryDeployer,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


@knot
async def emit_current() -> ModelManifest:
    return ModelManifest(model_id="current-v1", algorithm="logistic")


@knot
async def emit_candidate() -> ModelManifest:
    return ModelManifest(model_id="candidate-v2", algorithm="random_forest")


def _make_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


def _make_model(model_id: str) -> ModelManifest:
    return ModelManifest(model_id=model_id, algorithm="logistic")


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_fraction_out_of_range(self) -> None:
        with Tapestry():
            k = CanaryDeployer.__new__(CanaryDeployer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                current=_make_model("current-v1"),
                candidate=_make_model("candidate-v2"),
                split=_make_split(),
                canary_fraction=1.1,
                primary_metric="accuracy",
            )

    async def test_rejects_empty_primary_metric(self) -> None:
        with Tapestry():
            k = CanaryDeployer.__new__(CanaryDeployer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                current=_make_model("current-v1"),
                candidate=_make_model("candidate-v2"),
                split=_make_split(),
                canary_fraction=0.1,
                primary_metric="",
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_comparison_report(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            current = emit_current(_config=KnotConfig(id="cur"))
            candidate = emit_candidate(_config=KnotConfig(id="cand"))
            CanaryDeployer(
                current=current,
                candidate=candidate,
                split=split,
                canary_fraction=0.1,
                primary_metric="accuracy",
                _config=KnotConfig(id="canary"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["canary"]
        assert "current_score" in out
        assert "candidate_score" in out
        assert out["canary_fraction"] == 0.1
        assert out["recommendation"] in ("promote", "rollback")
