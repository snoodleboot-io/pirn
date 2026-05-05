"""Tests for :class:`DuckdbDeduplicate`."""

from __future__ import annotations
import unittest

import duckdb

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch
from pirn.domains.data.frames.duckdb.duckdb_deduplicate import DuckdbDeduplicate
from pirn.tapestry import Tapestry


@knot
async def emit_with_dups() -> DuckdbDataBatch:
    connection = duckdb.connect(database=":memory:")
    connection.execute(
        "CREATE TABLE t AS "
        "SELECT * FROM (VALUES "
        "(1, 1, 'a'), "
        "(2, 1, 'b'), "
        "(1, 2, 'a-v2'), "
        "(3, 1, 'c'), "
        "(2, 2, 'b-v2')"
        ") AS v(id, version, name)"
    )
    return DuckdbDataBatch(
        relation=connection.table("t"), connection=connection
    )


def _make_batch() -> DuckdbDataBatch:
    connection = duckdb.connect(database=":memory:")
    connection.execute(
        "CREATE TABLE t AS SELECT * FROM (VALUES (1, 'a'), (1, 'b')) AS v(id, name)"
    )
    return DuckdbDataBatch(relation=connection.table("t"), connection=connection)


class TestDuckdbDeduplicate(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_first_per_key(self) -> None:
        with Tapestry() as t:
            batch = emit_with_dups(_config=KnotConfig(id="batch"))
            DuckdbDeduplicate(
                batch=batch, keys=("id",), _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["dedup"]
        rows = out.relation.fetchall()
        ids = [row[0] for row in rows]
        names = [row[2] for row in rows]
        assert ids == [1, 2, 3]
        assert names == ["a", "b", "c"]

    async def test_composite_key(self) -> None:
        with Tapestry() as t:
            batch = emit_with_dups(_config=KnotConfig(id="batch"))
            DuckdbDeduplicate(
                batch=batch, keys=("id", "version"),
                _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["dedup"]
        rows = out.relation.fetchall()
        assert len(rows) == 5  # composite key already unique


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_keys_from_upstream_knot(self) -> None:
        @knot
        async def emit_keys() -> tuple:
            return ("id",)

        with Tapestry() as t:
            batch = emit_with_dups(_config=KnotConfig(id="batch"))
            keys_knot = emit_keys(_config=KnotConfig(id="keys"))
            DuckdbDeduplicate(
                batch=batch, keys=keys_knot, _config=KnotConfig(id="dedup"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["dedup"]
        rows = out.relation.fetchall()
        assert len(rows) == 3


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: object) -> DuckdbDeduplicate:
        @knot
        async def upstream() -> DuckdbDataBatch:
            return _make_batch()

        with Tapestry():
            batch = upstream(_config=KnotConfig(id="up"))
            return DuckdbDeduplicate(
                batch=batch, keys=("id",), _config=KnotConfig(id="d"), **kwargs,
            )

    async def test_rejects_empty_keys(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(batch=_make_batch(), keys=())

    async def test_rejects_string_keys_argument(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "sequence"):
            await k.process(batch=_make_batch(), keys="id")  # type: ignore[arg-type]

    async def test_rejects_unsafe_key(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await k.process(batch=_make_batch(), keys=("id; DROP TABLE",))
