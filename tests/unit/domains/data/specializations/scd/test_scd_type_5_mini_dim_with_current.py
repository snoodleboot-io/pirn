"""Tests for :class:`ScdType5MiniDimWithCurrent`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.scd.scd_type_5_mini_dim_with_current import (
    ScdType5MiniDimWithCurrent,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def source_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE customers ("
        "  id INTEGER PRIMARY KEY,"
        "  income_band TEXT NOT NULL,"
        "  credit_score INTEGER NOT NULL"
        ")"
    )
    await pool.execute_many(
        "INSERT INTO customers (id, income_band, credit_score) VALUES (?, ?, ?)",
        [(1, "high", 800), (2, "low", 600)],
    )
    yield pool
    await pool.close()


@pytest.fixture
async def main_pool(tmp_path) -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=str(tmp_path / "main5.db")))
    await pool.execute(
        "CREATE TABLE customers ("
        "  id INTEGER PRIMARY KEY,"
        "  mini_dim_sk INTEGER,"
        "  current_mini_dim_sk INTEGER"
        ")"
    )
    await pool.execute_many(
        "INSERT INTO customers (id) VALUES (?)",
        [(1,), (2,)],
    )
    yield pool
    await pool.close()


@pytest.fixture
async def mini_pool(tmp_path) -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=str(tmp_path / "mini5.db")))
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
    def test_rejects_non_pool(
        self, main_pool: SqlitePool, mini_pool: SqlitePool
    ) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            ScdType5MiniDimWithCurrent(
                source_pool="bad",  # type: ignore[arg-type]
                source_query="SELECT 1",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                current_mini_dim_sk_column="current_mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd5"),
            )

    def test_rejects_invalid_current_column(
        self,
        source_pool: SqlitePool,
        main_pool: SqlitePool,
        mini_pool: SqlitePool,
    ) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            ScdType5MiniDimWithCurrent(
                source_pool=source_pool,
                source_query="SELECT 1",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                current_mini_dim_sk_column="bad column",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd5"),
            )


@pytest.mark.asyncio
class TestScdType5Behaviour:
    async def test_sets_both_fk_and_current_sk(
        self,
        source_pool: SqlitePool,
        main_pool: SqlitePool,
        mini_pool: SqlitePool,
    ) -> None:
        with Tapestry() as t:
            ScdType5MiniDimWithCurrent(
                source_pool=source_pool,
                source_query="SELECT id, income_band, credit_score FROM customers",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                current_mini_dim_sk_column="current_mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd5"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await main_pool.fetch_all(
            "SELECT id, mini_dim_sk, current_mini_dim_sk FROM customers ORDER BY id"
        )
        for row in rows:
            assert row[1] is not None
            assert row[2] is not None
            assert row[1] == row[2]

    async def test_reuses_mini_dim_rows(
        self,
        source_pool: SqlitePool,
        main_pool: SqlitePool,
        mini_pool: SqlitePool,
    ) -> None:
        with Tapestry() as t:
            ScdType5MiniDimWithCurrent(
                source_pool=source_pool,
                source_query="SELECT id, income_band, credit_score FROM customers",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                current_mini_dim_sk_column="current_mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd5"),
            )
        assert (await t.run(RunRequest())).succeeded
        with Tapestry() as t2:
            ScdType5MiniDimWithCurrent(
                source_pool=source_pool,
                source_query="SELECT id, income_band, credit_score FROM customers",
                main_pool=main_pool,
                main_table="customers",
                main_key_columns=("id",),
                fact_fk_column="mini_dim_sk",
                current_mini_dim_sk_column="current_mini_dim_sk",
                mini_pool=mini_pool,
                mini_table="customer_profile",
                mini_dim_attributes=("income_band", "credit_score"),
                _config=KnotConfig(id="scd5"),
            )
        assert (await t2.run(RunRequest())).succeeded
        count = await mini_pool.fetch_all("SELECT COUNT(*) FROM customer_profile")
        assert count[0][0] == 2
