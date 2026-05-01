"""Tests for :class:`DuckdbFilter`."""

from __future__ import annotations

import duckdb
import pytest

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


@pytest.mark.asyncio
class TestDuckdbFilter:
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


class TestConstruction:
    def test_rejects_non_string_predicate(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="SQL string"):
                DuckdbFilter(
                    batch=batch,
                    predicate=lambda r: True,  # type: ignore[arg-type]
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_empty_predicate(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(ValueError, match="empty"):
                DuckdbFilter(
                    batch=batch, predicate="   ",
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_obvious_injection(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(ValueError, match="forbidden"):
                DuckdbFilter(
                    batch=batch,
                    predicate="1 = 1; DROP TABLE users",
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_line_comment(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(ValueError, match="forbidden"):
                DuckdbFilter(
                    batch=batch,
                    predicate="active -- skip rest",
                    _config=KnotConfig(id="f"),
                )
