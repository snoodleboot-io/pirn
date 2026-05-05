"""Tests for :class:`CrossValidator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.data_prep.cross_validator import CrossValidator
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_dataset() -> MLDataset:
    return MLDataset(
        name="customers",
        feature_names=("a",),
        row_count=100,
        source_uri="db://x",
    )


class TestCrossValidatorHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_k_folds(self) -> None:
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            CrossValidator(
                dataset=dataset,
                k=5,
                random_seed=42,
                _config=KnotConfig(id="cv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out: tuple[DataSplit, ...] = result.outputs["cv"]
        assert isinstance(out, tuple)
        assert len(out) == 5
        for split in out:
            assert isinstance(split, DataSplit)
            assert split.validation is None
            assert split.train.row_count + split.test.row_count == 100


class TestCrossValidatorConstruction(unittest.TestCase):
    def test_rejects_k_below_two(self) -> None:
        with Tapestry():
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            with self.assertRaisesRegex(ValueError, "k must be >= 2"):
                CrossValidator(
                    dataset=dataset,
                    k=1,
                    _config=KnotConfig(id="bad"),
                )
