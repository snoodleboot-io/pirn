"""Tests for :class:`PerformanceTriggeredRetrainer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.production.performance_triggered_retrainer import (
    PerformanceTriggeredRetrainer,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


def _fixtures():
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    split = SplitManifest(train=train, test=test)
    model = ModelManifest(
        model_id="m1", algorithm="rf", feature_names=("a",), target_name="y"
    )
    return model, split


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_metric(self) -> None:
        with Tapestry():
            k = PerformanceTriggeredRetrainer.__new__(PerformanceTriggeredRetrainer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, metric="", threshold=0.8)

    async def test_rejects_empty_algorithm(self) -> None:
        with Tapestry():
            k = PerformanceTriggeredRetrainer.__new__(PerformanceTriggeredRetrainer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                model=model,
                split=split,
                metric="accuracy",
                threshold=0.8,
                algorithm="",
            )
