"""Tests for :class:`DuckdbRename`."""

from __future__ import annotations
import unittest

import duckdb

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch
from pirn.domains.data.frames.duckdb.duckdb_rename import DuckdbRename
from pirn.tapestry import Tapestry


@knot
async def emit_users() -> DuckdbDataBatch:
    connection = duckdb.connect(database=":memory:")
    connection.execute(
        "CREATE TABLE users AS "
        "SELECT * FROM (VALUES (1, 'alice', 'EU'), (2, 'bob', 'US')) "
        "AS v(user_id, user_name, region)"
    )
    return DuckdbDataBatch(
        relation=connection.table("users"), connection=connection
    )


def _make_batch() -> DuckdbDataBatch:
    connection = duckdb.connect(database=":memory:")
    connection.execute(
        "CREATE TABLE t AS SELECT * FROM (VALUES (1, 'alice')) AS v(user_id, name)"
    )
    return DuckdbDataBatch(relation=connection.table("t"), connection=connection)


class TestDuckdbRename(unittest.IsolatedAsyncioTestCase):
    async def test_renames_columns(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DuckdbRename(
                batch=batch,
                mapping={"user_id": "id", "user_name": "name"},
                _config=KnotConfig(id="renamed"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["renamed"]
        assert set(out.column_names) == {"id", "name", "region"}

    async def test_unknown_columns_are_silently_ignored(self) -> None:
        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            DuckdbRename(
                batch=batch,
                mapping={"user_id": "id", "absent": "x"},
                _config=KnotConfig(id="renamed"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["renamed"]
        assert "id" in out.column_names
        assert "x" not in out.column_names


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_mapping_from_upstream_knot(self) -> None:
        @knot
        async def emit_mapping() -> dict:
            return {"user_id": "id", "user_name": "name"}

        with Tapestry() as t:
            batch = emit_users(_config=KnotConfig(id="users"))
            mapping_knot = emit_mapping(_config=KnotConfig(id="mapping"))
            DuckdbRename(
                batch=batch,
                mapping=mapping_knot,
                _config=KnotConfig(id="renamed"),
            )
        result = await t.run(RunRequest())
        out: DuckdbDataBatch = result.outputs["renamed"]
        assert set(out.column_names) == {"id", "name", "region"}


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: object) -> DuckdbRename:
        @knot
        async def upstream() -> DuckdbDataBatch:
            return _make_batch()

        with Tapestry():
            batch = upstream(_config=KnotConfig(id="up"))
            return DuckdbRename(
                batch=batch, mapping={"user_id": "id"},
                _config=KnotConfig(id="r"), **kwargs,
            )

    async def test_rejects_empty_mapping(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "non-empty"):
            await k.process(batch=_make_batch(), mapping={})

    async def test_rejects_non_mapping(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "non-empty"):
            await k.process(batch=_make_batch(), mapping="bad")  # type: ignore[arg-type]

    async def test_rejects_injection_in_mapping_value(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "forbidden token"):
            await k.process(
                batch=_make_batch(),
                mapping={"user_id": 'b"; DROP TABLE users; --'},
            )

    async def test_rejects_injection_in_mapping_key(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(ValueError, "forbidden token"):
            await k.process(
                batch=_make_batch(),
                mapping={'user_id"; DROP TABLE t --': "id"},
            )
