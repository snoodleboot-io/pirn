"""Tests for :class:`ResidualAnalyzer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.residual_analyzer import (
    ResidualAnalyzer,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


@knot
async def emit_model() -> ModelManifest:
    return ModelManifest(model_id="m1", algorithm="linear", feature_names=("a",))


def _make_knot() -> ResidualAnalyzer:
    with Tapestry():
        split = emit_split(_config=KnotConfig(id="split"))
        model = emit_model(_config=KnotConfig(id="model"))
        k = ResidualAnalyzer(
            model=model,
            split=split,
            n_bins=20,
            _config=KnotConfig(id="res"),
        )
    return k


def _fixtures() -> tuple[ModelManifest, SplitManifest]:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    split = SplitManifest(train=train, test=test)
    model = ModelManifest(model_id="m1", algorithm="linear", feature_names=("a",))
    return model, split


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_n_bins_less_than_two(self) -> None:
        knot = _make_knot()
        model, split = _fixtures()
        with self.assertRaisesRegex(ValueError, "n_bins"):
            await knot.process(model=model, split=split, n_bins=1)


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
