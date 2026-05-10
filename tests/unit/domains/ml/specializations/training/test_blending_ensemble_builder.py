"""Unit tests for :class:`BlendingEnsembleBuilder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.training.blending_ensemble_builder import (
    BlendingEnsembleBuilder,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


def _make_knot() -> BlendingEnsembleBuilder:
    with Tapestry():
        k = BlendingEnsembleBuilder.__new__(BlendingEnsembleBuilder)
        object.__setattr__(k, "_config", KnotConfig(id="beb"))
    return k


def _split():
    from pirn.domains.ml.types.split_manifest import SplitManifest
    from pirn.domains.ml.types.dataset_manifest import DatasetManifest

    return SplitManifest(
        train=DatasetManifest(name="tr", feature_names=["x"], target_name="y", row_count=10, source_uri="mem://"),
        test=DatasetManifest(name="te", feature_names=["x"], target_name="y", row_count=5, source_uri="mem://"),
    )


class TestBlendingEnsembleBuilderValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_fewer_than_two_algorithms(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), base_algorithms=["rf"], metrics=["accuracy"])

    async def test_rejects_empty_metrics(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), base_algorithms=["rf", "xgb"], metrics=[])


class TestBlendingEnsembleBuilderConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            BlendingEnsembleBuilder(
                split=_KnotStub(_config=KnotConfig(id="s")),
                base_algorithms=["rf", "xgb"],
                metrics=["accuracy"],
                _config=KnotConfig(id="beb"),
            )
        self.assertIsNotNone(t._store.get("beb"))
