"""Unit tests for :class:`_FeatureStoreReaderKnot`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.feature_store_provider import FeatureStoreProvider
from pirn.domains.ml.specializations.feature_engineering._feature_store_reader_knot import (
    _FeatureStoreReaderKnot,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.tapestry import Tapestry


class _StubStore(FeatureStoreProvider):
    async def get_features(self, entity_keys, feature_names):
        return [dict.fromkeys(feature_names, 0.0) for _ in entity_keys]

    async def write_features(self, features) -> int:
        return 0

    async def close(self) -> None:
        pass


class _SplitSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("x",), row_count=5)
        return SplitManifest(train=ds, test=ds)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_extends_feature_names(self) -> None:
        with Tapestry() as t:
            src = _SplitSource(_config=KnotConfig(id="src"))
            _FeatureStoreReaderKnot(
                split=src,
                feature_store=_StubStore(),
                entity_keys=["id"],
                feature_names=["f1", "f2"],
                _config=KnotConfig(id="fsr"),
            )
        result = await t.run(RunRequest())
        split = result.outputs["fsr"]
        self.assertIsInstance(split, SplitManifest)
        self.assertIn("f1", split.train.feature_names)
        self.assertIn("f2", split.train.feature_names)
