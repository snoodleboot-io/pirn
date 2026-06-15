"""Unit tests for :class:`SelfSupervisedPretrainer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.training.self_supervised_pretrainer import (
    SelfSupervisedPretrainer,
)


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


def _make_knot() -> SelfSupervisedPretrainer:
    with Tapestry():
        k = SelfSupervisedPretrainer.__new__(SelfSupervisedPretrainer)
        object.__setattr__(k, "_config", KnotConfig(id="ssp"))
    return k


def _split():
    from pirn_ml.types.dataset_manifest import DatasetManifest
    from pirn_ml.types.split_manifest import SplitManifest

    return SplitManifest(
        train=DatasetManifest(name="tr", feature_names=["x"], target_name="y", row_count=10, source_uri="mem://"),
        test=DatasetManifest(name="te", feature_names=["x"], target_name="y", row_count=5, source_uri="mem://"),
    )


class TestSelfSupervisedPretrainerValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_pretrain_algorithm(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), pretrain_algorithm="", finetune_algorithm="logistic", metrics=["accuracy"])

    async def test_rejects_empty_finetune_algorithm(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), pretrain_algorithm="masked", finetune_algorithm="", metrics=["accuracy"])

    async def test_rejects_empty_metrics(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), pretrain_algorithm="masked", finetune_algorithm="logistic", metrics=[])


class TestSelfSupervisedPretrainerConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            SelfSupervisedPretrainer(
                split=_KnotStub(_config=KnotConfig(id="s")),
                pretrain_algorithm="masked",
                finetune_algorithm="logistic",
                metrics=["accuracy"],
                _config=KnotConfig(id="ssp"),
            )
        self.assertIsNotNone(t._store.get("ssp"))
