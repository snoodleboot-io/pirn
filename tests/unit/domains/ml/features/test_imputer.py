"""Tests for :class:`Imputer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.features.imputer import Imputer
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("age",), row_count=10)
    test = MLDataset(name="d:test", feature_names=("age",), row_count=5)
    return DataSplit(train=train, test=test)


class TestImputerHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_imputed_split(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            Imputer(
                split=split,
                columns=("age",),
                method="median",
                _config=KnotConfig(id="imp"),
            )
        result = await t.run(RunRequest())
        out: DataSplit = result.outputs["imp"]
        assert out.train.name.endswith(":imputed_median")


class TestImputerConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_constant_method_without_value(self) -> None:
        train = MLDataset(name="d:train", feature_names=("age",), row_count=10)
        test = MLDataset(name="d:test", feature_names=("age",), row_count=5)
        split = DataSplit(train=train, test=test)
        with Tapestry():
            k = Imputer.__new__(Imputer)
            object.__setattr__(k, "_config", KnotConfig(id="bad"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, columns=("age",), method="constant")
