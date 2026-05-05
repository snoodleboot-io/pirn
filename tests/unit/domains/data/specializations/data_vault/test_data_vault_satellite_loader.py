"""Tests for :class:`DataVaultSatelliteLoader`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.data_vault.data_vault_satellite_loader import (
    DataVaultSatelliteLoader,
)
from pirn.tapestry import Tapestry

_SOURCE_QUERY = "SELECT hub_hk, hash_diff, name, email FROM raw_customer_attr"
_TARGET_TABLE = "sat_customer"
_HUB_HASH_KEY_COLUMN = "hub_hk"
_ATTRIBUTE_COLUMNS = ("name", "email")
_RECORD_SOURCE = "crm"


async def _make_pools() -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute(
        "CREATE TABLE raw_customer_attr ("
        "  hub_hk TEXT NOT NULL,"
        "  hash_diff TEXT NOT NULL,"
        "  name TEXT NOT NULL,"
        "  email TEXT NOT NULL"
        ")"
    )
    await src.execute_many(
        "INSERT INTO raw_customer_attr (hub_hk, hash_diff, name, email) VALUES (?, ?, ?, ?)",
        [("hk_1", "diff_a", "Alice", "alice@example.com")],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute(
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
    return src, tgt


def _make_knot(src: SqlitePool, tgt: SqlitePool) -> DataVaultSatelliteLoader:
    return DataVaultSatelliteLoader(
        source_pool=src,
        source_query=_SOURCE_QUERY,
        target_pool=tgt,
        target_table=_TARGET_TABLE,
        hub_hash_key_column=_HUB_HASH_KEY_COLUMN,
        attribute_columns=_ATTRIBUTE_COLUMNS,
        hash_diff_column="hash_diff",
        load_date_column="load_date",
        load_end_date_column="load_end_date",
        record_source_column="record_source",
        record_source=_RECORD_SOURCE,
        _config=KnotConfig(id="sat"),
    )


class TestDataVaultSatelliteLoader(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_first_run_inserts_row(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all(
            "SELECT hub_hk, name, load_end_date FROM sat_customer"
        )
        assert len(rows) == 1
        assert rows[0] == ("hk_1", "Alice", None)

    async def test_rerun_with_same_diff_is_noop(self) -> None:
        for run_id in ("sat_r1", "sat_r2"):
            with Tapestry() as t:
                DataVaultSatelliteLoader(
                    source_pool=self.src,
                    source_query=_SOURCE_QUERY,
                    target_pool=self.tgt,
                    target_table=_TARGET_TABLE,
                    hub_hash_key_column=_HUB_HASH_KEY_COLUMN,
                    attribute_columns=_ATTRIBUTE_COLUMNS,
                    hash_diff_column="hash_diff",
                    load_date_column="load_date",
                    load_end_date_column="load_end_date",
                    record_source_column="record_source",
                    record_source=_RECORD_SOURCE,
                    _config=KnotConfig(id=run_id),
                )
            assert (await t.run(RunRequest())).succeeded
        rows = await self.tgt.fetch_all("SELECT hub_hk FROM sat_customer")
        assert len(rows) == 1

    async def test_changed_diff_closes_old_and_inserts_new(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        assert (await t.run(RunRequest())).succeeded
        await self.src.execute(
            "UPDATE raw_customer_attr SET hash_diff = ?, email = ? WHERE hub_hk = ?",
            ("diff_b", "alice2@example.com", "hk_1"),
        )
        with Tapestry() as t2:
            DataVaultSatelliteLoader(
                source_pool=self.src,
                source_query=_SOURCE_QUERY,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                hub_hash_key_column=_HUB_HASH_KEY_COLUMN,
                attribute_columns=_ATTRIBUTE_COLUMNS,
                hash_diff_column="hash_diff",
                load_date_column="load_date",
                load_end_date_column="load_end_date",
                record_source_column="record_source",
                record_source=_RECORD_SOURCE,
                _config=KnotConfig(id="sat_v2"),
            )
        assert (await t2.run(RunRequest())).succeeded
        all_rows = await self.tgt.fetch_all(
            "SELECT load_end_date FROM sat_customer ORDER BY load_date"
        )
        assert len(all_rows) == 2
        assert all_rows[0][0] is not None
        assert all_rows[1][0] is None


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_source_query_from_upstream_knot(self) -> None:
        @knot
        async def emit_query() -> str:
            return _SOURCE_QUERY

        with Tapestry() as t:
            q_knot = emit_query(_config=KnotConfig(id="q"))
            DataVaultSatelliteLoader(
                source_pool=self.src,
                source_query=q_knot,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                hub_hash_key_column=_HUB_HASH_KEY_COLUMN,
                attribute_columns=_ATTRIBUTE_COLUMNS,
                hash_diff_column="hash_diff",
                load_date_column="load_date",
                load_end_date_column="load_end_date",
                record_source_column="record_source",
                record_source=_RECORD_SOURCE,
                _config=KnotConfig(id="sat"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["sat"]["rows_inserted"] == 1


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> DataVaultSatelliteLoader:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "hub_hash_key_column": _HUB_HASH_KEY_COLUMN,
            "attribute_columns": _ATTRIBUTE_COLUMNS,
            "hash_diff_column": "hash_diff",
            "load_date_column": "load_date",
            "load_end_date_column": "load_end_date",
            "record_source_column": "record_source",
            "record_source": _RECORD_SOURCE,
        }
        defaults.update(kwargs)
        with Tapestry():
            return DataVaultSatelliteLoader(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: DataVaultSatelliteLoader, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "hub_hash_key_column": _HUB_HASH_KEY_COLUMN,
            "attribute_columns": _ATTRIBUTE_COLUMNS,
            "hash_diff_column": "hash_diff",
            "load_date_column": "load_date",
            "load_end_date_column": "load_end_date",
            "record_source_column": "record_source",
            "record_source": _RECORD_SOURCE,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool_source(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, source_pool="bad")

    async def test_rejects_non_pool_target(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, target_pool="bad")

    async def test_rejects_empty_source_query(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_query"):
            await self._call(k, source_query="")

    async def test_rejects_empty_record_source(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "record_source"):
            await self._call(k, record_source="")

    async def test_rejects_invalid_target_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, target_table="bad; DROP")

    async def test_rejects_attribute_clashing_with_envelope(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "clash"):
            await self._call(k, attribute_columns=("load_date",))
