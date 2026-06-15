"""Unit tests for :class:`FineTuningTrainer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.training.fine_tuning_trainer import (
    FineTuningTrainer,
)


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


def _make_knot() -> FineTuningTrainer:
    with Tapestry():
        k = FineTuningTrainer.__new__(FineTuningTrainer)
        object.__setattr__(k, "_config", KnotConfig(id="ftt"))
    return k


def _split():
    from pirn_ml.types.dataset_manifest import DatasetManifest
    from pirn_ml.types.split_manifest import SplitManifest

    return SplitManifest(
        train=DatasetManifest(name="tr", feature_names=["x"], target_name="y", row_count=10, source_uri="mem://"),
        test=DatasetManifest(name="te", feature_names=["x"], target_name="y", row_count=5, source_uri="mem://"),
    )


class TestFineTuningTrainerValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_pretrained_model_id(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), pretrained_model_id="", algorithm="nn", metrics=["accuracy"])

    async def test_rejects_frozen_layers_negative(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), pretrained_model_id="base-model", algorithm="nn", metrics=["accuracy"], frozen_layers=-1)

    async def test_rejects_empty_metrics(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), pretrained_model_id="base", algorithm="nn", metrics=[])


class TestFineTuningTrainerConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            FineTuningTrainer(
                split=_KnotStub(_config=KnotConfig(id="s")),
                pretrained_model_id="resnet50",
                algorithm="nn",
                metrics=["accuracy"],
                frozen_layers=5,
                _config=KnotConfig(id="ftt"),
            )
        self.assertIsNotNone(t._store.get("ftt"))
