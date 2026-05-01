"""Tests for :class:`DuckdbDeduplicate`."""

from __future__ import annotations

import duckdb
import pytest

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


@pytest.mark.asyncio
class TestDuckdbDeduplicate:
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


class TestConstruction:
    def test_rejects_string_keys_argument(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="sequence"):
                DuckdbDeduplicate(
                    batch=batch, keys="id",  # type: ignore[arg-type]
                    _config=KnotConfig(id="d"),
                )

    def test_rejects_empty_keys(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(ValueError, match="non-empty"):
                DuckdbDeduplicate(
                    batch=batch, keys=(), _config=KnotConfig(id="d"),
                )

    def test_rejects_unsafe_key(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(ValueError, match="plain identifier"):
                DuckdbDeduplicate(
                    batch=batch, keys=("id; DROP TABLE",),
                    _config=KnotConfig(id="d"),
                )
