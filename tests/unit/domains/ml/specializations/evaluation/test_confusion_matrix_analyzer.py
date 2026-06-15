"""Tests for :class:`ConfusionMatrixAnalyzer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.confusion_matrix_analyzer import (
    ConfusionMatrixAnalyzer,
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
    return ModelManifest(model_id="m1", algorithm="logistic", feature_names=("a",))


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_model(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaises(TypeError):
                ConfusionMatrixAnalyzer(
                    model="bad",  # type: ignore[arg-type]
                    split=split,
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_confusion_matrix_and_per_class_metrics(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            ConfusionMatrixAnalyzer(
                model=model,
                split=split,
                class_labels=("neg", "pos"),
                _config=KnotConfig(id="cm"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["cm"]
        assert "confusion_matrix" in out
        assert "per_class" in out
        assert "macro_f1" in out
        assert "neg" in out["per_class"]
        assert "pos" in out["per_class"]
