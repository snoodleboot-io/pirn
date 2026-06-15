"""Unit tests for :class:`InteractionFeatureGenerator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.interaction_feature_generator import (
    InteractionFeatureGenerator,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


class _SplitSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("a", "b"), row_count=10)
        return SplitManifest(train=ds, test=ds)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> InteractionFeatureGenerator:
        k = InteractionFeatureGenerator.__new__(InteractionFeatureGenerator)
        object.__setattr__(k, "_config", KnotConfig(id="ifg"))
        return k

    def _make_split(self) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("a", "b"), row_count=10)
        return SplitManifest(train=ds, test=ds)

    async def test_rejects_empty_column_pairs(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), column_pairs=[])

    async def test_rejects_invalid_pair_format(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                column_pairs=[("a",)],  # type: ignore[list-item]
            )

    async def test_appends_interaction_features(self) -> None:
        with Tapestry() as t:
            src = _SplitSource(_config=KnotConfig(id="src"))
            InteractionFeatureGenerator(
                split=src,
                column_pairs=[("a", "b")],
                _config=KnotConfig(id="ifg"),
            )
        result = await t.run(RunRequest())
        split = result.outputs["ifg"]
        self.assertIsInstance(split, SplitManifest)
        self.assertIn("a_x_b", split.train.feature_names)
