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
    return ModelManifest(
        model_id="m1",
        algorithm="ridge",
        feature_names=("a",),
        target_name="y",
    )


def _fixtures():
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    split = SplitManifest(train=train, test=test)
    model = ModelManifest(
        model_id="m1", algorithm="ridge", feature_names=("a",), target_name="y"
    )
    return model, split


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_n_bins_less_than_two(self) -> None:
        with Tapestry():
            k = ResidualAnalyzer.__new__(ResidualAnalyzer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, n_bins=1)

    async def test_rejects_float_n_bins(self) -> None:
        with Tapestry():
            k = ResidualAnalyzer.__new__(ResidualAnalyzer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, n_bins=5.5)  # type: ignore[arg-type]


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_residual_diagnostics(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            ResidualAnalyzer(
                model=model,
                split=split,
                n_bins=10,
                _config=KnotConfig(id="ra"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["ra"]
        assert "histogram" in out
        assert len(out["histogram"]) == 10
        assert "durbin_watson" in out
        assert "heteroscedastic" in out
