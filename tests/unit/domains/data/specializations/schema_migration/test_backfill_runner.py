"""Tests for :class:`BackfillRunner`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.schema_migration.backfill_runner import (
    BackfillRunner,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def source_pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, val TEXT)")
    await p.execute_many(
        "INSERT INTO events VALUES (?, ?)",
        [(i, f"v{i}") for i in range(1, 6)],
    )
    yield p
    await p.close()


@pytest.fixture
async def target_pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, val TEXT)")
    yield p
    await p.close()


class TestConstruction:
    def test_rejects_non_pool_source(self, target_pool: SqlitePool) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            BackfillRunner(
                source_pool="bad",  # type: ignore[arg-type]
                target_pool=target_pool,
                source_table="events",
                key_column="id",
                batch_query_template="SELECT * FROM events WHERE id > ? LIMIT ?",
                _config=KnotConfig(id="bf"),
            )

    def test_rejects_non_positive_batch_size(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="batch_size"):
            BackfillRunner(
                source_pool=source_pool,
                target_pool=target_pool,
                source_table="events",
                key_column="id",
                batch_query_template="SELECT * FROM events WHERE id > ? LIMIT ?",
                batch_size=0,
                _config=KnotConfig(id="bf"),
            )

    def test_rejects_invalid_table_identifier(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            BackfillRunner(
                source_pool=source_pool,
                target_pool=target_pool,
                source_table="my events",
                key_column="id",
                batch_query_template="SELECT * FROM events WHERE id > ? LIMIT ?",
                _config=KnotConfig(id="bf"),
            )


@pytest.mark.asyncio
class TestBehaviour:
    async def test_processes_all_rows_in_batches(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            BackfillRunner(
                source_pool=source_pool,
                target_pool=target_pool,
                source_table="events",
                key_column="id",
                batch_query_template=(
                    "SELECT * FROM events WHERE id > ? ORDER BY id LIMIT ?"
                ),
                batch_size=2,
                resume_from_key=0,
                _config=KnotConfig(id="bf"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["bf"]
        assert output["rows_processed"] == 5
        assert output["batches_processed"] == 3
        assert output["last_processed_key"] == 5

    async def test_resume_from_key_skips_processed(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            BackfillRunner(
                source_pool=source_pool,
                target_pool=target_pool,
                source_table="events",
                key_column="id",
                batch_query_template=(
                    "SELECT * FROM events WHERE id > ? ORDER BY id LIMIT ?"
                ),
                batch_size=1000,
                resume_from_key=3,
                _config=KnotConfig(id="bf-resume"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["bf-resume"]
        assert output["rows_processed"] == 2
