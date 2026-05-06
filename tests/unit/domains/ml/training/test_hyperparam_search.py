"""Tests for :class:`HyperparamSearch`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.training.hyperparam_search import HyperparamSearch
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
    return DataSplit(train=train, test=test)


class TestHyperparamSearchHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_best_candidate(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            HyperparamSearch(
                split=split,
                algorithm="logreg",
                search_space={"C": (0.1, 1.0, 10.0)},
                strategy="grid",
                random_seed=7,
                _config=KnotConfig(id="search"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out: TrainedModel = result.outputs["search"]
        assert isinstance(out, TrainedModel)
        assert out.algorithm == "logreg"
        assert "C" in out.hyperparameters


class TestHyperparamSearchConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_search_space(self) -> None:
        train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
        test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
        split = DataSplit(train=train, test=test)
        with Tapestry():
            k = HyperparamSearch.__new__(HyperparamSearch)
            object.__setattr__(k, "_config", KnotConfig(id="bad"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, algorithm="logreg", search_space={})

    async def test_rejects_empty_value_list(self) -> None:
        train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
        test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
        split = DataSplit(train=train, test=test)
        with Tapestry():
            k = HyperparamSearch.__new__(HyperparamSearch)
            object.__setattr__(k, "_config", KnotConfig(id="bad"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, algorithm="logreg", search_space={"C": ()})
