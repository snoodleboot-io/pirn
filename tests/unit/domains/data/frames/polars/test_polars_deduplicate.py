"""Tests for :class:`PolarsDeduplicate`."""

from __future__ import annotations

import unittest

import polars as pl

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn.domains.data.frames.polars.polars_deduplicate import PolarsDeduplicate
from pirn.tapestry import Tapestry


@knot
async def emit_with_dups() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {
                "id":      [1, 2, 1, 3, 2],
                "version": [1, 1, 2, 1, 2],
                "name":    ["a", "b", "a-v2", "c", "b-v2"],
            }
        )
    )


def _dup_batch() -> PolarsDataBatch:
    return PolarsDataBatch(
        frame=pl.DataFrame(
            {
                "id":   [1, 2, 1],
                "name": ["a", "b", "a-v2"],
            }
        )
    )


class TestPolarsDeduplicate(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_first_per_key(self) -> None:
        with Tapestry() as t:
            batch = emit_with_dups(_config=KnotConfig(id="batch"))
            PolarsDeduplicate(
                batch=batch, keys=("id",), _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["dedup"]
        assert tuple(out.frame["id"].to_list()) == (1, 2, 3)
        assert tuple(out.frame["name"].to_list()) == ("a", "b", "c")

    async def test_composite_key(self) -> None:
        with Tapestry() as t:
            batch = emit_with_dups(_config=KnotConfig(id="batch"))
            PolarsDeduplicate(
                batch=batch, keys=("id", "version"),
                _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["dedup"]
        assert out.row_count == 5  # composite key is unique


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_keys_from_upstream_knot(self) -> None:
        @knot
        async def emit_keys() -> object:
            return ("id",)

        with Tapestry() as t:
            batch = emit_with_dups(_config=KnotConfig(id="batch"))
            keys_knot = emit_keys(_config=KnotConfig(id="keys"))
            PolarsDeduplicate(
                batch=batch,
                keys=keys_knot,
                _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: PolarsDataBatch = result.outputs["dedup"]
        assert out.row_count == 3


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> PolarsDeduplicate:
        @knot
        async def empty() -> PolarsDataBatch:
            return PolarsDataBatch(frame=pl.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return PolarsDeduplicate(
                batch=batch, keys=("id",), _config=KnotConfig(id="d"), **kwargs
            )

    async def test_rejects_string_keys_argument(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "sequence"):
            await k.process(batch=_dup_batch(), keys="id")

    async def test_rejects_empty_keys(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(batch=_dup_batch(), keys=())

    async def test_rejects_blank_key_entry(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "non-empty string"):
            await k.process(batch=_dup_batch(), keys=("",))
