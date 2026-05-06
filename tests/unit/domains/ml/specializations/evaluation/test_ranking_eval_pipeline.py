"""Unit tests for :class:`RankingEvalPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.evaluation.ranking_eval_pipeline import (
    RankingEvalPipeline,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


def _make_knot() -> RankingEvalPipeline:
    with Tapestry():
        rp = RankingEvalPipeline(
            model=_KnotStub(_config=KnotConfig(id="m")),
            split=_KnotStub(_config=KnotConfig(id="s")),
            k=10,
            _config=KnotConfig(id="rp"),
        )
    return rp


def _fixtures() -> tuple[TrainedModel, DataSplit]:
    train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
    split = DataSplit(train=train, test=test)
    model = TrainedModel(model_id="m1", algorithm="als", feature_names=("a",))
    return model, split


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_k_less_than_1(self) -> None:
        knot = _make_knot()
        model, split = _fixtures()
        with self.assertRaises(ValueError):
            await knot.process(model=model, split=split, k=0)

    async def test_rejects_non_int_k(self) -> None:
        knot = _make_knot()
        model, split = _fixtures()
        with self.assertRaises(TypeError):
            await knot.process(model=model, split=split, k=5.0)  # type: ignore[arg-type]
