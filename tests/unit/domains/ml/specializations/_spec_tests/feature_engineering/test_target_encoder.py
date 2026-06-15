"""Tests for :class:`TargetEncoder`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.target_encoder import (
    TargetEncoder,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(
        name="d:train", feature_names=("city",), target_name="y", row_count=80
    )
    test = DatasetManifest(
        name="d:test", feature_names=("city",), target_name="y", row_count=20
    )
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    def _make_split(self) -> SplitManifest:
        train = DatasetManifest(
            name="d:train", feature_names=("city",), target_name="y", row_count=80
        )
        test = DatasetManifest(
            name="d:test", feature_names=("city",), target_name="y", row_count=20
        )
        return SplitManifest(train=train, test=test)

    async def test_rejects_empty_categorical_column(self) -> None:
        with Tapestry():
            k = TargetEncoder.__new__(TargetEncoder)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(), categorical_column="", target_column="y"
            )

    async def test_rejects_negative_smoothing(self) -> None:
        with Tapestry():
            k = TargetEncoder.__new__(TargetEncoder)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                categorical_column="city",
                target_column="y",
                smoothing=-0.1,
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_target_encoded_split(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            TargetEncoder(
                split=split,
                categorical_column="city",
                target_column="y",
                smoothing=2.0,
                _config=KnotConfig(id="te"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["te"]
        assert isinstance(out, SplitManifest)
        assert out.train.name.endswith("encoded_target")
