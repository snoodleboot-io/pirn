"""Unit tests for :class:`ABTestPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.production.ab_test_pipeline import ABTestPipeline
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


def _make_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


def _make_model(model_id: str) -> ModelManifest:
    return ModelManifest(model_id=model_id, algorithm="logistic", feature_names=("a",))


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_alpha_zero(self) -> None:
        with Tapestry():
            k = ABTestPipeline.__new__(ABTestPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                model_a=_make_model("a"),
                model_b=_make_model("b"),
                split=_make_split(),
                primary_metric="accuracy",
                alpha=0.0,
            )

    async def test_rejects_invalid_alpha_one(self) -> None:
        with Tapestry():
            k = ABTestPipeline.__new__(ABTestPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                model_a=_make_model("a"),
                model_b=_make_model("b"),
                split=_make_split(),
                primary_metric="accuracy",
                alpha=1.0,
            )

    async def test_rejects_empty_primary_metric(self) -> None:
        with Tapestry():
            k = ABTestPipeline.__new__(ABTestPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                model_a=_make_model("a"),
                model_b=_make_model("b"),
                split=_make_split(),
                primary_metric="",
                alpha=0.05,
            )
