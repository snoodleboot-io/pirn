"""Tests for :class:`DataVaultHubLoader`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.data_vault.data_vault_hub_loader import (
    DataVaultHubLoader,
)

_SOURCE_QUERY = "SELECT hk, customer_id FROM raw_customer"
_TARGET_TABLE = "hub_customer"
_HASH_KEY_COLUMN = "hub_hk"
_BUSINESS_KEY_COLUMNS = ("customer_id",)
_RECORD_SOURCE = "test_system"


async def _make_pools() -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute(
        "CREATE TABLE raw_customer ("
        "  hk TEXT NOT NULL,"
        "  customer_id INTEGER NOT NULL"
        ")"
    )
    await src.execute_many(
        "INSERT INTO raw_customer (hk, customer_id) VALUES (?, ?)",
        [("hk_1", 1), ("hk_2", 2)],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute(
        "CREATE TABLE hub_customer ("
        "  hub_hk TEXT PRIMARY KEY,"
        "  customer_id INTEGER NOT NULL,"
        "  load_date TEXT NOT NULL,"
        "  record_source TEXT NOT NULL"
        ")"
    )
    return src, tgt


def _make_knot(src: SqlitePool, tgt: SqlitePool) -> DataVaultHubLoader:
    return DataVaultHubLoader(
        source_pool=src,
        source_query=_SOURCE_QUERY,
        target_pool=tgt,
        target_table=_TARGET_TABLE,
        hash_key_column=_HASH_KEY_COLUMN,
        business_key_columns=_BUSINESS_KEY_COLUMNS,
        load_date_column="load_date",
        record_source_column="record_source",
        record_source=_RECORD_SOURCE,
        _config=KnotConfig(id="hub"),
    )


class TestDataVaultHubLoader(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_first_run_inserts_all_rows(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all(
            "SELECT hub_hk, customer_id FROM hub_customer ORDER BY customer_id"
        )
        assert rows == [("hk_1", 1), ("hk_2", 2)]

    async def test_second_run_is_noop_for_existing_keys(self) -> None:
        for run_id in ("hub_run1", "hub_run2"):
            with Tapestry() as t:
                DataVaultHubLoader(
                    source_pool=self.src,
                    source_query=_SOURCE_QUERY,
                    target_pool=self.tgt,
                    target_table=_TARGET_TABLE,
                    hash_key_column=_HASH_KEY_COLUMN,
                    business_key_columns=_BUSINESS_KEY_COLUMNS,
                    load_date_column="load_date",
                    record_source_column="record_source",
                    record_source=_RECORD_SOURCE,
                    _config=KnotConfig(id=run_id),
                )
            assert (await t.run(RunRequest())).succeeded
        rows = await self.tgt.fetch_all("SELECT hub_hk FROM hub_customer")
        assert len(rows) == 2

    async def test_new_key_inserted_incrementally(self) -> None:
        with Tapestry() as t:
            DataVaultHubLoader(
                source_pool=self.src,
                source_query="SELECT hk, customer_id FROM raw_customer WHERE customer_id = 1",
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                hash_key_column=_HASH_KEY_COLUMN,
                business_key_columns=_BUSINESS_KEY_COLUMNS,
                load_date_column="load_date",
                record_source_column="record_source",
                record_source=_RECORD_SOURCE,
                _config=KnotConfig(id="hub_partial"),
            )
        assert (await t.run(RunRequest())).succeeded
        with Tapestry() as t2:
            DataVaultHubLoader(
                source_pool=self.src,
                source_query=_SOURCE_QUERY,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                hash_key_column=_HASH_KEY_COLUMN,
                business_key_columns=_BUSINESS_KEY_COLUMNS,
                load_date_column="load_date",
                record_source_column="record_source",
                record_source=_RECORD_SOURCE,
                _config=KnotConfig(id="hub_full"),
            )
        assert (await t2.run(RunRequest())).succeeded
        rows = await self.tgt.fetch_all(
            "SELECT hub_hk FROM hub_customer ORDER BY customer_id"
        )
        assert len(rows) == 2

    async def test_load_date_and_record_source_populated(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        assert (await t.run(RunRequest())).succeeded
        rows = await self.tgt.fetch_all(
            "SELECT record_source, load_date FROM hub_customer"
        )
        assert rows[0][0] == _RECORD_SOURCE
        assert rows[0][1] is not None

    async def test_result_tracks_rows_inserted(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["rows_inserted"] == 2


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
            DataVaultHubLoader(
                source_pool=self.src,
                source_query=q_knot,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                hash_key_column=_HASH_KEY_COLUMN,
                business_key_columns=_BUSINESS_KEY_COLUMNS,
                load_date_column="load_date",
                record_source_column="record_source",
                record_source=_RECORD_SOURCE,
                _config=KnotConfig(id="hub"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["hub"]["rows_inserted"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> DataVaultHubLoader:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "hash_key_column": _HASH_KEY_COLUMN,
            "business_key_columns": _BUSINESS_KEY_COLUMNS,
            "load_date_column": "load_date",
            "record_source_column": "record_source",
            "record_source": _RECORD_SOURCE,
        }
        defaults.update(kwargs)
        with Tapestry():
            return DataVaultHubLoader(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: DataVaultHubLoader, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "hash_key_column": _HASH_KEY_COLUMN,
            "business_key_columns": _BUSINESS_KEY_COLUMNS,
            "load_date_column": "load_date",
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
            await self._call(k, target_table="bad; DROP TABLE x")

    async def test_rejects_business_key_clashing_with_envelope(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "clash"):
            await self._call(k, business_key_columns=("load_date",))
