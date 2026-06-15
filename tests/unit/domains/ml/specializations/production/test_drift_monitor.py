"""Unit tests for :class:`DriftMonitor`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.production.drift_monitor import DriftMonitor
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


def _make_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("f1", "f2"), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("f1", "f2"), row_count=20)
    return SplitManifest(train=train, test=test)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_columns(self) -> None:
        with Tapestry():
            k = DriftMonitor.__new__(DriftMonitor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                baseline=_make_split(),
                current=_make_split(),
                columns=(),
                threshold=0.1,
            )

    async def test_rejects_threshold_out_of_range(self) -> None:
        with Tapestry():
            k = DriftMonitor.__new__(DriftMonitor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                baseline=_make_split(),
                current=_make_split(),
                columns=("feature",),
                threshold=1.5,
            )
