"""Tests for :class:`InteractionFeatureGenerator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.interaction_feature_generator import (
    InteractionFeatureGenerator,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(
        name="d:train",
        feature_names=("age", "income"),
        target_name="y",
        row_count=80,
    )
    test = DatasetManifest(
        name="d:test",
        feature_names=("age", "income"),
        target_name="y",
        row_count=20,
    )
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    def _make_split(self) -> SplitManifest:
        train = DatasetManifest(
            name="d:train", feature_names=("age", "income"), target_name="y", row_count=80
        )
        test = DatasetManifest(
            name="d:test", feature_names=("age", "income"), target_name="y", row_count=20
        )
        return SplitManifest(train=train, test=test)

    async def test_rejects_empty_column_pairs(self) -> None:
        with Tapestry():
            k = InteractionFeatureGenerator.__new__(InteractionFeatureGenerator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), column_pairs=[])

    async def test_rejects_malformed_pair(self) -> None:
        with Tapestry():
            k = InteractionFeatureGenerator.__new__(InteractionFeatureGenerator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(), column_pairs=[("age",)]  # type: ignore[list-item]
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_appends_interaction_feature_names(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            InteractionFeatureGenerator(
                split=split,
                column_pairs=[("age", "income")],
                _config=KnotConfig(id="ifg"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["ifg"]
        assert isinstance(out, SplitManifest)
        features = out.train.feature_names
        assert "age_x_income" in features
        assert "age" in features
        assert "income" in features
        assert "interactions" in out.train.name
