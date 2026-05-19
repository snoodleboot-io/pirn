"""Tests for :class:`DuckdbFilter`."""

from __future__ import annotations

import unittest

try:
    import duckdb  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("duckdb not installed") from _e

import duckdb

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch
from pirn.domains.data.frames.duckdb.duckdb_filter import DuckdbFilter
from pirn.tapestry import Tapestry


@knot
async def emit_users() -> DuckdbDataBatch:
    connection = duckdb.connect(database=":memory:")
    connection.execute(
        "CREATE TABLE users AS "
        "SELECT * FROM (VALUES "
        "(1, TRUE,  'EU'), "
        "(2, FALSE, 'US'), "
        "(3, TRUE,  'US'), "
        "(4, FALSE, 'EU')"
        ") AS v(id, active, region)"
    )
    return DuckdbDataBatch(
        relation=connection.table("users"), connection=connection
    )


def _make_batch() -> DuckdbDataBatch:
    connection = duckdb.connect(database=":memory:")
    connection.execute(
        "CREATE TABLE t AS SELECT * FROM (VALUES (1, TRUE), (2, FALSE)) AS v(id, active)"
    )
    return DuckdbDataBatch(relation=connection.table("t"), connection=connection)


class TestDuckdbFilter(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_rows_matching_predicate(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DuckdbFilter(
                batch=batch, predicate="active",
                _config=KnotConfig(id="active"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["active"]
        ids = sorted(row[0] for row in out.relation.fetchall())
        assert ids == [1, 3]

    async def test_compound_predicate(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DuckdbFilter(
                batch=batch,
                predicate="region = 'EU' AND active",
                _config=KnotConfig(id="active_eu"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["active_eu"]
        ids = sorted(row[0] for row in out.relation.fetchall())
        assert ids == [1]


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_predicate_from_upstream_knot(self) -> None:
        @knot
        async def emit_predicate() -> str:
            return "active"

        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            pred_knot = emit_predicate(_config=KnotConfig(id="pred"))
            DuckdbFilter(
                batch=batch,
                predicate=pred_knot,
                _config=KnotConfig(id="filtered"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["filtered"]
        ids = sorted(row[0] for row in out.relation.fetchall())
        assert ids == [1, 3]


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: object) -> DuckdbFilter:
        @knot
        async def upstream() -> DuckdbDataBatch:
            return _make_batch()

        with Tapestry():
            batch = upstream(_config=KnotConfig(id="up"))
            return DuckdbFilter(batch=batch, predicate="active", _config=KnotConfig(id="f"), **kwargs)

    async def test_rejects_non_string_predicate(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "SQL string"):
            await k.process(batch=_make_batch(), predicate=lambda r: True)

    async def test_rejects_empty_predicate(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "empty"):
            await k.process(batch=_make_batch(), predicate="   ")

    async def test_rejects_obvious_injection(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "forbidden"):
            await k.process(batch=_make_batch(), predicate="1 = 1; DROP TABLE users")

    async def test_rejects_line_comment(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "forbidden"):
            await k.process(batch=_make_batch(), predicate="active -- skip rest")
