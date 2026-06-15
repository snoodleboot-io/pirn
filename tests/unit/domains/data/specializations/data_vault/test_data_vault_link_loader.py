"""Tests for :class:`DataVaultLinkLoader`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.data_vault.data_vault_link_loader import (
    DataVaultLinkLoader,
)

_SOURCE_QUERY = "SELECT link_hk, customer_hk, product_hk FROM raw_order"
_TARGET_TABLE = "link_order"
_LINK_HASH_KEY_COLUMN = "link_hk"
_HUB_HASH_KEY_COLUMNS = ("customer_hk", "product_hk")
_RECORD_SOURCE = "order_system"


async def _make_pools() -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute(
        "CREATE TABLE raw_order ("
        "  link_hk TEXT NOT NULL,"
        "  customer_hk TEXT NOT NULL,"
        "  product_hk TEXT NOT NULL"
        ")"
    )
    await src.execute_many(
        "INSERT INTO raw_order (link_hk, customer_hk, product_hk) VALUES (?, ?, ?)",
        [("lhk_1", "chk_1", "phk_a"), ("lhk_2", "chk_2", "phk_b")],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute(
        "CREATE TABLE link_order ("
        "  link_hk TEXT PRIMARY KEY,"
        "  customer_hk TEXT NOT NULL,"
        "  product_hk TEXT NOT NULL,"
        "  load_date TEXT NOT NULL,"
        "  record_source TEXT NOT NULL"
        ")"
    )
    return src, tgt


def _make_knot(src: SqlitePool, tgt: SqlitePool) -> DataVaultLinkLoader:
    return DataVaultLinkLoader(
        source_pool=src,
        source_query=_SOURCE_QUERY,
        target_pool=tgt,
        target_table=_TARGET_TABLE,
        link_hash_key_column=_LINK_HASH_KEY_COLUMN,
        hub_hash_key_columns=_HUB_HASH_KEY_COLUMNS,
        load_date_column="load_date",
        record_source_column="record_source",
        record_source=_RECORD_SOURCE,
        _config=KnotConfig(id="link"),
    )


class TestDataVaultLinkLoader(unittest.IsolatedAsyncioTestCase):
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
            "SELECT link_hk FROM link_order ORDER BY link_hk"
        )
        assert rows == [("lhk_1",), ("lhk_2",)]

    async def test_second_run_is_noop_for_existing_links(self) -> None:
        for run_id in ("link_r1", "link_r2"):
            with Tapestry() as t:
                DataVaultLinkLoader(
                    source_pool=self.src,
                    source_query=_SOURCE_QUERY,
                    target_pool=self.tgt,
                    target_table=_TARGET_TABLE,
                    link_hash_key_column=_LINK_HASH_KEY_COLUMN,
                    hub_hash_key_columns=_HUB_HASH_KEY_COLUMNS,
                    load_date_column="load_date",
                    record_source_column="record_source",
                    record_source=_RECORD_SOURCE,
                    _config=KnotConfig(id=run_id),
                )
            assert (await t.run(RunRequest())).succeeded
        rows = await self.tgt.fetch_all("SELECT link_hk FROM link_order")
        assert len(rows) == 2

    async def test_load_date_and_record_source_populated(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        assert (await t.run(RunRequest())).succeeded
        rows = await self.tgt.fetch_all(
            "SELECT record_source, load_date FROM link_order"
        )
        assert rows[0][0] == _RECORD_SOURCE
        assert rows[0][1] is not None


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
            DataVaultLinkLoader(
                source_pool=self.src,
                source_query=q_knot,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                link_hash_key_column=_LINK_HASH_KEY_COLUMN,
                hub_hash_key_columns=_HUB_HASH_KEY_COLUMNS,
                load_date_column="load_date",
                record_source_column="record_source",
                record_source=_RECORD_SOURCE,
                _config=KnotConfig(id="link"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["link"]["rows_inserted"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> DataVaultLinkLoader:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "link_hash_key_column": _LINK_HASH_KEY_COLUMN,
            "hub_hash_key_columns": _HUB_HASH_KEY_COLUMNS,
            "load_date_column": "load_date",
            "record_source_column": "record_source",
            "record_source": _RECORD_SOURCE,
        }
        defaults.update(kwargs)
        with Tapestry():
            return DataVaultLinkLoader(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: DataVaultLinkLoader, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "link_hash_key_column": _LINK_HASH_KEY_COLUMN,
            "hub_hash_key_columns": _HUB_HASH_KEY_COLUMNS,
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

    async def test_rejects_invalid_target_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, target_table="bad; DROP TABLE x")

    async def test_rejects_hub_key_clashing_with_link_key(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "clash"):
            await self._call(k, hub_hash_key_columns=("link_hk",))
