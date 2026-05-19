"""Tests for :class:`DataDriftDetector`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.data_drift_detector import (
    DataDriftDetector,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.tapestry import Tapestry


@knot
async def emit_reference() -> SplitManifest:
    train = DatasetManifest(name="r:train", feature_names=("a", "b"), row_count=800)
    test = DatasetManifest(name="r:test", feature_names=("a", "b"), row_count=200)
    return SplitManifest(train=train, test=test)


@knot
async def emit_current() -> SplitManifest:
    train = DatasetManifest(name="c:train", feature_names=("a", "b"), row_count=900)
    test = DatasetManifest(name="c:test", feature_names=("a", "b"), row_count=100)
    return SplitManifest(train=train, test=test)


def _make_reference() -> SplitManifest:
    train = DatasetManifest(name="r:train", feature_names=("a", "b"), row_count=800)
    test = DatasetManifest(name="r:test", feature_names=("a", "b"), row_count=200)
    return SplitManifest(train=train, test=test)


def _make_current() -> SplitManifest:
    train = DatasetManifest(name="c:train", feature_names=("a", "b"), row_count=900)
    test = DatasetManifest(name="c:test", feature_names=("a", "b"), row_count=100)
    return SplitManifest(train=train, test=test)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_features(self) -> None:
        with Tapestry():
            k = DataDriftDetector.__new__(DataDriftDetector)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                reference=_make_reference(),
                current=_make_current(),
                features=(),
                psi_threshold=0.2,
            )

    async def test_rejects_negative_threshold(self) -> None:
        with Tapestry():
            k = DataDriftDetector.__new__(DataDriftDetector)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                reference=_make_reference(),
                current=_make_current(),
                features=("a",),
                psi_threshold=-0.1,
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_drift_report(self) -> None:
        with Tapestry() as t:
            ref = emit_reference(_config=KnotConfig(id="r"))
            cur = emit_current(_config=KnotConfig(id="c"))
            DataDriftDetector(
                reference=ref,
                current=cur,
                features=("a", "b"),
                psi_threshold=0.2,
                _config=KnotConfig(id="dd"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["dd"]
        assert set(out["psi"].keys()) == {"a", "b"}
        assert set(out["ks_statistic"].keys()) == {"a", "b"}
        assert isinstance(out["drift_detected"], bool)
        assert isinstance(out["drifted_features"], list)
