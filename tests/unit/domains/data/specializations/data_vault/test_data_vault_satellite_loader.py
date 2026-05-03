"""Tests for :class:`DataVaultSatelliteLoader`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.data_vault.data_vault_satellite_loader import (
    DataVaultSatelliteLoader,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def source_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE raw_customer_attr ("
        "  hub_hk TEXT NOT NULL,"
        "  hash_diff TEXT NOT NULL,"
        "  name TEXT NOT NULL,"
        "  email TEXT NOT NULL"
        ")"
    )
    await pool.execute_many(
        "INSERT INTO raw_customer_attr (hub_hk, hash_diff, name, email) VALUES (?, ?, ?, ?)",
        [("hk_1", "diff_a", "Alice", "alice@example.com")],
    )
    yield pool
    await pool.close()


@pytest.fixture
async def target_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE sat_customer ("
        "  hub_hk TEXT NOT NULL,"
        "  hash_diff TEXT NOT NULL,"
        "  name TEXT NOT NULL,"
        "  email TEXT NOT NULL,"
        "  load_date TEXT NOT NULL,"
        "  load_end_date TEXT,"
        "  record_source TEXT NOT NULL"
        ")"
    )
    yield pool
    await pool.close()


def _run_loader(
    source_pool: SqlitePool,
    target_pool: SqlitePool,
    *,
    knot_id: str,
    query: str = "SELECT hub_hk, hash_diff, name, email FROM raw_customer_attr",
) -> DataVaultSatelliteLoader:
    with Tapestry() as t:
        DataVaultSatelliteLoader(
            source_pool=source_pool,
            source_query=query,
            target_pool=target_pool,
            target_table="sat_customer",
            hub_hash_key_column="hub_hk",
            attribute_columns=("name", "email"),
            record_source="crm",
            _config=KnotConfig(id=knot_id),
        )
    return t


class TestConstruction:
    def test_rejects_non_pool_source(self, target_pool: SqlitePool) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            with Tapestry():
                DataVaultSatelliteLoader(
                    source_pool="bad",  # type: ignore[arg-type]
                    source_query="SELECT 1",
                    target_pool=target_pool,
                    target_table="sat_customer",
                    hub_hash_key_column="hub_hk",
                    attribute_columns=("name",),
                    record_source="src",
                    _config=KnotConfig(id="sat"),
                )

    def test_rejects_empty_record_source(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="record_source"):
            with Tapestry():
                DataVaultSatelliteLoader(
                    source_pool=source_pool,
                    source_query="SELECT 1",
                    target_pool=target_pool,
                    target_table="sat_customer",
                    hub_hash_key_column="hub_hk",
                    attribute_columns=("name",),
                    record_source="",
                    _config=KnotConfig(id="sat"),
                )

    def test_rejects_attribute_clashing_with_envelope(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="clash"):
            with Tapestry():
                DataVaultSatelliteLoader(
                    source_pool=source_pool,
                    source_query="SELECT 1",
                    target_pool=target_pool,
                    target_table="sat_customer",
                    hub_hash_key_column="hub_hk",
                    attribute_columns=("load_date",),
                    record_source="src",
                    _config=KnotConfig(id="sat"),
                )

    def test_rejects_invalid_target_table(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            with Tapestry():
                DataVaultSatelliteLoader(
                    source_pool=source_pool,
                    source_query="SELECT 1",
                    target_pool=target_pool,
                    target_table="bad; DROP",
                    hub_hash_key_column="hub_hk",
                    attribute_columns=("name",),
                    record_source="src",
                    _config=KnotConfig(id="sat"),
                )


@pytest.mark.asyncio
class TestSatelliteLoaderBehaviour:
    async def test_first_run_inserts_row(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            DataVaultSatelliteLoader(
                source_pool=source_pool,
                source_query="SELECT hub_hk, hash_diff, name, email FROM raw_customer_attr",
                target_pool=target_pool,
                target_table="sat_customer",
                hub_hash_key_column="hub_hk",
                attribute_columns=("name", "email"),
                record_source="crm",
                _config=KnotConfig(id="sat_first"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT hub_hk, name, load_end_date FROM sat_customer"
        )
        assert len(rows) == 1
        assert rows[0] == ("hk_1", "Alice", None)

    async def test_rerun_with_same_diff_is_noop(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        for run_id in ("sat_r1", "sat_r2"):
            with Tapestry() as t:
                DataVaultSatelliteLoader(
                    source_pool=source_pool,
                    source_query="SELECT hub_hk, hash_diff, name, email FROM raw_customer_attr",
                    target_pool=target_pool,
                    target_table="sat_customer",
                    hub_hash_key_column="hub_hk",
                    attribute_columns=("name", "email"),
                    record_source="crm",
                    _config=KnotConfig(id=run_id),
                )
            assert (await t.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all("SELECT hub_hk FROM sat_customer")
        assert len(rows) == 1

    async def test_changed_diff_closes_old_and_inserts_new(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            DataVaultSatelliteLoader(
                source_pool=source_pool,
                source_query="SELECT hub_hk, hash_diff, name, email FROM raw_customer_attr",
                target_pool=target_pool,
                target_table="sat_customer",
                hub_hash_key_column="hub_hk",
                attribute_columns=("name", "email"),
                record_source="crm",
                _config=KnotConfig(id="sat_v1"),
            )
        assert (await t.run(RunRequest())).succeeded
        await source_pool.execute(
            "UPDATE raw_customer_attr SET hash_diff = ?, email = ? WHERE hub_hk = ?",
            ("diff_b", "alice2@example.com", "hk_1"),
        )
        with Tapestry() as t2:
            DataVaultSatelliteLoader(
                source_pool=source_pool,
                source_query="SELECT hub_hk, hash_diff, name, email FROM raw_customer_attr",
                target_pool=target_pool,
                target_table="sat_customer",
                hub_hash_key_column="hub_hk",
                attribute_columns=("name", "email"),
                record_source="crm",
                _config=KnotConfig(id="sat_v2"),
            )
        assert (await t2.run(RunRequest())).succeeded
        all_rows = await target_pool.fetch_all(
            "SELECT load_end_date FROM sat_customer ORDER BY load_date"
        )
        assert len(all_rows) == 2
        assert all_rows[0][0] is not None
        assert all_rows[1][0] is None
