"""Tests for :class:`Scaler`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.features.scaler import Scaler
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


def _split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


@knot
async def emit_split() -> SplitManifest:
    return _split()


class TestScalerHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_renamed_split(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            Scaler(
                split=split,
                columns=("a",),
                method="standardise",
                _config=KnotConfig(id="scaler"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out: SplitManifest = result.outputs["scaler"]
        assert out.train.name.endswith(":scaled_standardise")
        assert out.test.name.endswith(":scaled_standardise")
        assert out.train.row_count == 80
        assert out.test.row_count == 20


class TestScalerConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_unknown_method(self) -> None:
        split = _split()
        with Tapestry():
            k = Scaler.__new__(Scaler)
            object.__setattr__(k, "_config", KnotConfig(id="bad"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, columns=("a",), method="bogus")
