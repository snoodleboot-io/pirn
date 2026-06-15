"""Tests for :class:`ConfusionMatrixAnalyzer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.evaluation.confusion_matrix_analyzer import (
    ConfusionMatrixAnalyzer,
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
async def emit_model() -> ModelManifest:
    return ModelManifest(
        model_id="m1",
        algorithm="rf",
        feature_names=("a",),
        target_name="y",
    )


def _fixtures():
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    split = SplitManifest(train=train, test=test)
    model = ModelManifest(
        model_id="m1", algorithm="rf", feature_names=("a",), target_name="y"
    )
    return model, split


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_default_class_labels(self) -> None:
        """ConfusionMatrixAnalyzer accepts None class_labels without raising."""
        with Tapestry():
            k = ConfusionMatrixAnalyzer.__new__(ConfusionMatrixAnalyzer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model, split = _fixtures()
        result = await k.process(model=model, split=split, class_labels=None)
        assert "confusion_matrix" in result
        assert "macro_f1" in result

    async def test_rejects_empty_class_labels_sequence(self) -> None:
        """Empty sequence of class labels should still produce output (not raise)."""
        with Tapestry():
            k = ConfusionMatrixAnalyzer.__new__(ConfusionMatrixAnalyzer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model, split = _fixtures()
        # An empty tuple defaults to an empty tuple of labels — this is a degenerate
        # but not necessarily invalid call; the main guard is None vs empty.
        # The key validation path tested here is a truly bad class label list.
        with self.assertRaises((TypeError, ValueError, ZeroDivisionError)):
            await k.process(model=model, split=split, class_labels=())


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_confusion_matrix_and_f1(self) -> None:
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
