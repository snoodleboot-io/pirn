"""Tests for :class:`DuckdbRename`."""

from __future__ import annotations

import duckdb
import pytest

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


@pytest.mark.asyncio
class TestDuckdbRename:
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


class TestConstruction:
    def test_rejects_empty_mapping(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="non-empty"):
                DuckdbRename(batch=batch, mapping={}, _config=KnotConfig(id="r"))

    def test_rejects_injection_in_mapping_value(self) -> None:
        @knot
        async def empty() -> DuckdbDataBatch:
            connection = duckdb.connect(database=":memory:")
            return DuckdbDataBatch(
                relation=connection.sql("SELECT NULL AS x WHERE FALSE"),
                connection=connection,
            )

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(ValueError, match="forbidden token"):
                DuckdbRename(
                    batch=batch,
                    mapping={"a": "b\"; DROP TABLE users; --"},
                    _config=KnotConfig(id="r"),
                )
