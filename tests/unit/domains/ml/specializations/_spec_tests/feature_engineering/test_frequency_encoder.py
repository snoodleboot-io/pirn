"""Tests for :class:`FrequencyEncoder`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.feature_engineering.frequency_encoder import (
    FrequencyEncoder,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


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
            k = FrequencyEncoder.__new__(FrequencyEncoder)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), categorical_column="")

    async def test_rejects_negative_default_frequency(self) -> None:
        with Tapestry():
            k = FrequencyEncoder.__new__(FrequencyEncoder)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(), categorical_column="city", default_frequency=-0.1
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_freq_encoded_split(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            FrequencyEncoder(
                split=split,
                categorical_column="city",
                _config=KnotConfig(id="fe"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["fe"]
        assert isinstance(out, SplitManifest)
        assert "freq_encoded" in out.train.name
