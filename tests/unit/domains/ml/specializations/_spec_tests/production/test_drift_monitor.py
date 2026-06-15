"""Tests for :class:`DriftMonitor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.production.drift_monitor import (
    DriftMonitor,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def emit_baseline() -> SplitManifest:
    train = DatasetManifest(name="b:train", feature_names=("a", "b"), row_count=800)
    test = DatasetManifest(name="b:test", feature_names=("a", "b"), row_count=200)
    return SplitManifest(train=train, test=test)


@knot
async def emit_current() -> SplitManifest:
    train = DatasetManifest(name="c:train", feature_names=("a", "b"), row_count=900)
    test = DatasetManifest(name="c:test", feature_names=("a", "b"), row_count=100)
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_threshold_above_one(self) -> None:
        with Tapestry():
            k = DriftMonitor.__new__(DriftMonitor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        baseline = SplitManifest(
            train=DatasetManifest(name="b:train", feature_names=("a", "b"), row_count=800),
            test=DatasetManifest(name="b:test", feature_names=("a", "b"), row_count=200),
        )
        current = SplitManifest(
            train=DatasetManifest(name="c:train", feature_names=("a", "b"), row_count=900),
            test=DatasetManifest(name="c:test", feature_names=("a", "b"), row_count=100),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(baseline=baseline, current=current, columns=("a",), threshold=1.5)

    async def test_rejects_empty_columns(self) -> None:
        with Tapestry():
            k = DriftMonitor.__new__(DriftMonitor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        baseline = SplitManifest(
            train=DatasetManifest(name="b:train", feature_names=("a", "b"), row_count=800),
            test=DatasetManifest(name="b:test", feature_names=("a", "b"), row_count=200),
        )
        current = SplitManifest(
            train=DatasetManifest(name="c:train", feature_names=("a", "b"), row_count=900),
            test=DatasetManifest(name="c:test", feature_names=("a", "b"), row_count=100),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(baseline=baseline, current=current, columns=(), threshold=0.1)


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_per_column_scores_and_flag(self) -> None:
        with Tapestry() as t:
            baseline = emit_baseline(_config=KnotConfig(id="b"))
            current = emit_current(_config=KnotConfig(id="c"))
            DriftMonitor(
                baseline=baseline,
                current=current,
                columns=("a", "b"),
                threshold=0.5,
                _config=KnotConfig(id="drift"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["drift"]
        assert set(out["scores"].keys()) == {"a", "b"}
        assert isinstance(out["drift_detected"], bool)
        for score in out["scores"].values():
            assert 0.0 <= score <= 1.0
