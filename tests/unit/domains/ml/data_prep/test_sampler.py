"""Tests for :class:`Sampler`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.data_prep.sampler import Sampler
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_dataset() -> MLDataset:
    return MLDataset(
        name="customers",
        feature_names=("a",),
        row_count=1000,
        source_uri="db://x",
    )


def _make_dataset(row_count: int = 1000) -> MLDataset:
    return MLDataset(
        name="customers",
        feature_names=("a",),
        row_count=row_count,
        source_uri="db://x",
    )


class TestSamplerHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_caps_to_n(self) -> None:
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            Sampler(
                dataset=dataset,
                n=100,
                _config=KnotConfig(id="sample"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out: MLDataset = result.outputs["sample"]
        assert out.row_count == 100
        assert out.name.endswith(":sampled")

    async def test_uses_fraction(self) -> None:
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="dataset"))
            Sampler(
                dataset=dataset,
                fraction=0.25,
                _config=KnotConfig(id="sample"),
            )
        result = await t.run(RunRequest())
        out: MLDataset = result.outputs["sample"]
        assert out.row_count == 250


class TestSamplerProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> Sampler:
        with Tapestry():
            s = Sampler.__new__(Sampler)
            object.__setattr__(s, "_config", KnotConfig(id="x"))
        return s

    async def test_rejects_both_n_and_fraction(self) -> None:
        s = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await s.process(dataset=_make_dataset(), n=10, fraction=0.1)

    async def test_rejects_neither_n_nor_fraction(self) -> None:
        s = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await s.process(dataset=_make_dataset())
