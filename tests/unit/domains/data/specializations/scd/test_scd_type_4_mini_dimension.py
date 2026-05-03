"""Tests for :class:`ScdType4MiniDimension`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.scd.scd_type_4_mini_dimension import (
    ScdType4MiniDimension,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def source_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE customers ("
        "  id INTEGER PRIMARY KEY,"
        "  name TEXT NOT NULL,"
        "  income_band TEXT NOT NULL,"
        "  credit_score INTEGER NOT NULL"
        ")"
    )
    await pool.execute_many(
        "INSERT INTO customers (id, name, income_band, credit_score) VALUES (?, ?, ?, ?)",
        [(1, "Alice", "high", 800), (2, "Bob", "low", 600)],
    )
    yield pool
    await pool.close()


@pytest.fixture
async def main_pool(tmp_path) -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=str(tmp_path / "main.db")))
    await pool.execute(
        "CREATE TABLE customers ("
        "  id INTEGER PRIMARY KEY,"
        "  name TEXT NOT NULL,"
        "  mini_dim_sk INTEGER"
        ")"
    )
    await pool.execute_many(
        "INSERT INTO customers (id, name) VALUES (?, ?)",
        [(1, "Alice"), (2, "Bob")],
    )
    yield pool
    await pool.close()


@pytest.fixture
async def mini_pool(tmp_path) -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=str(tmp_path / "mini.db")))
    await pool.execute(
        "CREATE TABLE customer_profile ("
        "  mini_dim_sk INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  income_band TEXT NOT NULL,"
        "  credit_score INTEGER NOT NULL"
        ")"
    )
    yield pool
    await pool.close()


class TestConstruction:
    def test_rejects_non_pool_source(
        self, main_pool: SqlitePool, mini_pool: SqlitePool
    ) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            ScdType4MiniDimension(
                source_pool="bad",  # type: ignore[arg-type]
                source_query="SELECT 1",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd4"),
            )

    def test_rejects_empty_source_query(
        self,
        source_pool: SqlitePool,
        main_pool: SqlitePool,
        mini_pool: SqlitePool,
    ) -> None:
        with pytest.raises(ValueError, match="source_query"):
            ScdType4MiniDimension(
                source_pool=source_pool,
                source_query="",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd4"),
            )

    def test_rejects_invalid_identifier(
        self,
        source_pool: SqlitePool,
        main_pool: SqlitePool,
        mini_pool: SqlitePool,
    ) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            ScdType4MiniDimension(
                source_pool=source_pool,
                source_query="SELECT 1",
                main_pool=main_pool,
                main_table="bad table",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd4"),
            )


@pytest.mark.asyncio
class TestScdType4Behaviour:
    async def test_inserts_new_mini_dim_rows(
        self,
        source_pool: SqlitePool,
        main_pool: SqlitePool,
        mini_pool: SqlitePool,
    ) -> None:
        with Tapestry() as t:
            ScdType4MiniDimension(
                source_pool=source_pool,
                source_query="SELECT id, income_band, credit_score FROM customers",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd4"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        mini_rows = await mini_pool.fetch_all(
            "SELECT income_band, credit_score FROM customer_profile ORDER BY mini_dim_sk"
        )
        assert len(mini_rows) == 2
        assert ("high", 800) in mini_rows
        assert ("low", 600) in mini_rows

    async def test_reuses_existing_mini_dim_rows(
        self,
        source_pool: SqlitePool,
        main_pool: SqlitePool,
        mini_pool: SqlitePool,
    ) -> None:
        with Tapestry() as t:
            ScdType4MiniDimension(
                source_pool=source_pool,
                source_query="SELECT id, income_band, credit_score FROM customers",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd4"),
            )
        assert (await t.run(RunRequest())).succeeded
        with Tapestry() as t2:
            ScdType4MiniDimension(
                source_pool=source_pool,
                source_query="SELECT id, income_band, credit_score FROM customers",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd4"),
            )
        assert (await t2.run(RunRequest())).succeeded
        mini_count = await mini_pool.fetch_all(
            "SELECT COUNT(*) FROM customer_profile"
        )
        assert mini_count[0][0] == 2

    async def test_updates_main_dim_fk(
        self,
        source_pool: SqlitePool,
        main_pool: SqlitePool,
        mini_pool: SqlitePool,
    ) -> None:
        with Tapestry() as t:
            ScdType4MiniDimension(
                source_pool=source_pool,
                source_query="SELECT id, income_band, credit_score FROM customers",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd4"),
            )
        assert (await t.run(RunRequest())).succeeded
        fk_rows = await main_pool.fetch_all(
            "SELECT id, mini_dim_sk FROM customers ORDER BY id"
        )
        for row in fk_rows:
            assert row[1] is not None
