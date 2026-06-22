"""Tests for :class:`DataDriftDetector`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.production.data_drift_detector import (
    DataDriftDetector,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


def _split_fixture(name_prefix: str = "d") -> SplitManifest:
    train = DatasetManifest(name=f"{name_prefix}:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name=f"{name_prefix}:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_features(self) -> None:
        with Tapestry():
            k = DataDriftDetector.__new__(DataDriftDetector)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        reference = _split_fixture("ref")
        current = _split_fixture("cur")
        with self.assertRaises((TypeError, ValueError)):
            await k.process(reference=reference, current=current, features=())

    async def test_rejects_negative_psi_threshold(self) -> None:
        with Tapestry():
            k = DataDriftDetector.__new__(DataDriftDetector)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        reference = _split_fixture("ref")
        current = _split_fixture("cur")
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                reference=reference,
                current=current,
                features=("a",),
                psi_threshold=-0.1,
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_drift_report(self) -> None:
        with Tapestry() as t:
            reference = emit_split(_config=KnotConfig(id="ref"))
            current = emit_split(_config=KnotConfig(id="cur"))
            DataDriftDetector(
                reference=reference,
                current=current,
                features=("a",),
                psi_threshold=0.2,
                _config=KnotConfig(id="ddd"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["ddd"]
        assert "psi" in out
        assert "ks_statistic" in out
        assert "drifted_features" in out
        assert "drift_detected" in out
