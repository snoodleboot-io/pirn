"""Tests for :class:`BridgeTableBuilder`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.dimensional.bridge_table_builder import (
    BridgeTableBuilder,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def source_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE account_product ("
        "  account_sk INTEGER NOT NULL,"
        "  product_sk INTEGER NOT NULL,"
        "  group_id INTEGER NOT NULL"
        ")"
    )
    await pool.execute_many(
        "INSERT INTO account_product (account_sk, product_sk, group_id) VALUES (?, ?, ?)",
        [(1, 10, 1), (1, 20, 1), (2, 30, 2)],
    )
    yield pool
    await pool.close()


@pytest.fixture
async def target_pool(tmp_path) -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=str(tmp_path / "bridge.db")))
    await pool.execute(
        "CREATE TABLE bridge_account_product ("
        "  account_sk INTEGER NOT NULL,"
        "  product_sk INTEGER NOT NULL,"
        "  weight_factor REAL NOT NULL"
        ")"
    )
    yield pool
    await pool.close()


class TestConstruction:
    def test_rejects_non_pool(self, target_pool: SqlitePool) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            BridgeTableBuilder(
                source_pool="bad",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=target_pool,
                bridge_table="bridge_account_product",
                left_key_columns=("account_sk",),
                right_key_columns=("product_sk",),
                group_key_columns=("account_sk",),
                _config=KnotConfig(id="bridge"),
            )

    def test_rejects_auto_weight_without_group_keys(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="group_key_columns"):
            BridgeTableBuilder(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                bridge_table="bridge_account_product",
                left_key_columns=("account_sk",),
                right_key_columns=("product_sk",),
                auto_weight=True,
                group_key_columns=None,
                _config=KnotConfig(id="bridge"),
            )

    def test_rejects_invalid_bridge_table_identifier(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            BridgeTableBuilder(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                bridge_table="bad table",
                left_key_columns=("account_sk",),
                right_key_columns=("product_sk",),
                group_key_columns=("account_sk",),
                _config=KnotConfig(id="bridge"),
            )


@pytest.mark.asyncio
class TestBridgeTableBuilderBehaviour:
    async def test_auto_weight_proportional(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            BridgeTableBuilder(
                source_pool=source_pool,
                source_query=(
                    "SELECT account_sk, product_sk, group_id "
                    "FROM account_product"
                ),
                target_pool=target_pool,
                bridge_table="bridge_account_product",
                left_key_columns=("account_sk",),
                right_key_columns=("product_sk",),
                group_key_columns=("account_sk",),
                source_columns=("account_sk", "product_sk", "group_id"),
                _config=KnotConfig(id="bridge"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT account_sk, weight_factor "
            "FROM bridge_account_product ORDER BY account_sk, product_sk"
        )
        assert len(rows) == 3
        account1_weights = [r[1] for r in rows if r[0] == 1]
        assert len(account1_weights) == 2
        for w in account1_weights:
            assert abs(w - 0.5) < 1e-9
        account2_weights = [r[1] for r in rows if r[0] == 2]
        assert len(account2_weights) == 1
        assert abs(account2_weights[0] - 1.0) < 1e-9

    async def test_rebuilds_on_second_run(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        for _ in range(2):
            with Tapestry() as t:
                BridgeTableBuilder(
                    source_pool=source_pool,
                    source_query=(
                        "SELECT account_sk, product_sk, group_id "
                        "FROM account_product"
                    ),
                    target_pool=target_pool,
                    bridge_table="bridge_account_product",
                    left_key_columns=("account_sk",),
                    right_key_columns=("product_sk",),
                    group_key_columns=("account_sk",),
                    source_columns=("account_sk", "product_sk", "group_id"),
                    _config=KnotConfig(id="bridge"),
                )
            assert (await t.run(RunRequest())).succeeded
        count = await target_pool.fetch_all(
            "SELECT COUNT(*) FROM bridge_account_product"
        )
        assert count[0][0] == 3

    async def test_manual_weight(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute(
            "CREATE TABLE manual_src ("
            "  account_sk INTEGER NOT NULL,"
            "  product_sk INTEGER NOT NULL,"
            "  weight_factor REAL NOT NULL"
            ")"
        )
        await pool.execute_many(
            "INSERT INTO manual_src VALUES (?, ?, ?)",
            [(1, 10, 0.3), (1, 20, 0.7)],
        )
        with Tapestry() as t:
            BridgeTableBuilder(
                source_pool=pool,
                source_query="SELECT account_sk, product_sk, weight_factor FROM manual_src",
                target_pool=target_pool,
                bridge_table="bridge_account_product",
                left_key_columns=("account_sk",),
                right_key_columns=("product_sk",),
                auto_weight=False,
                source_columns=("account_sk", "product_sk", "weight_factor"),
                _config=KnotConfig(id="bridge"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT weight_factor FROM bridge_account_product ORDER BY product_sk"
        )
        assert abs(rows[0][0] - 0.3) < 1e-9
        assert abs(rows[1][0] - 0.7) < 1e-9
        await pool.close()
