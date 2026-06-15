"""Tests for :class:`Encoder`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.features.encoder import Encoder
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("region",), row_count=10)
    test = DatasetManifest(name="d:test", feature_names=("region",), row_count=5)
    return SplitManifest(train=train, test=test)


class TestEncoderHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_encoded_split(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            Encoder(
                split=split,
                columns=("region",),
                method="onehot",
                _config=KnotConfig(id="enc"),
            )
        result = await t.run(RunRequest())
        out: SplitManifest = result.outputs["enc"]
        assert out.train.name.endswith(":encoded_onehot")


class TestEncoderProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_columns(self) -> None:
        encoder = Encoder.__new__(Encoder)
        object.__setattr__(encoder, "_config", KnotConfig(id="x"))
        train = DatasetManifest(name="d:train", feature_names=("region",), row_count=10)
        test = DatasetManifest(name="d:test", feature_names=("region",), row_count=5)
        split = SplitManifest(train=train, test=test)
        with self.assertRaisesRegex(ValueError, "columns must be non-empty"):
            await encoder.process(split=split, columns=(), method="onehot")
