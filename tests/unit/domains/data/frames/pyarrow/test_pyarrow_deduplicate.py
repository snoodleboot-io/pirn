"""Tests for :class:`PyarrowDeduplicate`."""

from __future__ import annotations

import unittest

try:
    import pyarrow  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyarrow not installed") from _e

import pyarrow as pa
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch
from pirn_data.frames.pyarrow.pyarrow_deduplicate import (
    PyarrowDeduplicate,
)


def _empty_batch() -> PyarrowDataBatch:
    return PyarrowDataBatch(table=pa.table({}))


@knot
async def emit_dupes() -> PyarrowDataBatch:
    return PyarrowDataBatch(
        table=pa.table(
            {
                "id":   [1, 1, 2, 2, 3],
                "name": ["a", "a2", "b", "b2", "c"],
            }
        )
    )


class TestPyarrowDeduplicate(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_first_occurrence(self) -> None:
        with Tapestry() as t:
            batch = emit_dupes(_config=KnotConfig(id="src"))
            PyarrowDeduplicate(
                batch=batch,
                keys=("id",),
                _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["dedup"]
        ids = out.table.column("id").to_pylist()
        names = out.table.column("name").to_pylist()
        assert ids == [1, 2, 3]
        assert names == ["a", "b", "c"]

    async def test_composite_keys(self) -> None:
        @knot
        async def emit_two_keys() -> PyarrowDataBatch:
            return PyarrowDataBatch(
                table=pa.table(
                    {
                        "region": ["EU", "EU", "US", "EU"],
                        "tier":   ["A",  "A",  "A",  "B"],
                        "rev":    [1,    2,    3,    4],
                    }
                )
            )

        with Tapestry() as t:
            batch = emit_two_keys(_config=KnotConfig(id="src"))
            PyarrowDeduplicate(
                batch=batch,
                keys=("region", "tier"),
                _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["dedup"]
        # 3 unique (region, tier) tuples; first-occurrence rev values are 1,3,4.
        assert sorted(out.table.column("rev").to_pylist()) == [1, 3, 4]

    async def test_empty_table_passes_through(self) -> None:
        @knot
        async def emit_empty() -> PyarrowDataBatch:
            return PyarrowDataBatch(
                table=pa.table({"id": pa.array([], type=pa.int64())})
            )

        with Tapestry() as t:
            batch = emit_empty(_config=KnotConfig(id="src"))
            PyarrowDeduplicate(
                batch=batch, keys=("id",),
                _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["dedup"]
        assert out.row_count == 0


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_keys_from_upstream_knot(self) -> None:
        @knot
        async def emit_keys() -> tuple:
            return ("id",)

        with Tapestry() as t:
            batch = emit_dupes(_config=KnotConfig(id="src"))
            keys_knot = emit_keys(_config=KnotConfig(id="keys"))
            PyarrowDeduplicate(
                batch=batch,
                keys=keys_knot,
                _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: PyarrowDataBatch = result.outputs["dedup"]
        assert out.table.column("id").to_pylist() == [1, 2, 3]
        assert out.table.column("name").to_pylist() == ["a", "b", "c"]


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> PyarrowDeduplicate:
        @knot
        async def empty() -> PyarrowDataBatch:
            return PyarrowDataBatch(table=pa.table({}))

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return PyarrowDeduplicate(
                batch=batch, _config=KnotConfig(id="d"), **kwargs
            )

    async def test_rejects_string_keys(self) -> None:
        k = self._make_knot(keys="id")
        with self.assertRaisesRegex(TypeError, "sequence"):
            await k.process(batch=_empty_batch(), keys="id")  # type: ignore[arg-type]

    async def test_rejects_empty_keys(self) -> None:
        k = self._make_knot(keys=())
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(batch=_empty_batch(), keys=())
