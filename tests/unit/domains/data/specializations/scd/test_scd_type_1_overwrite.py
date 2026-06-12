"""Tests for :class:`ScdType1Overwrite`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.scd.scd_type_1_overwrite import ScdType1Overwrite
from pirn.tapestry import Tapestry

_SOURCE_QUERY = "SELECT id, name FROM customers ORDER BY id"
_TARGET_TABLE = "customers"
_KEY_COLS = ("id",)
_NON_KEY_COLS = ("name",)


async def _make_pools() -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)")
    await src.execute_many(
        "INSERT INTO customers (id, name) VALUES (?, ?)",
        [(1, "Alice"), (2, "Bob")],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)")
    return src, tgt


def _make_knot(src: SqlitePool, tgt: SqlitePool) -> ScdType1Overwrite:
    return ScdType1Overwrite(
        source_pool=src,
        source_query=_SOURCE_QUERY,
        target_pool=tgt,
        target_table=_TARGET_TABLE,
        key_columns=_KEY_COLS,
        non_key_columns=_NON_KEY_COLS,
        _config=KnotConfig(id="scd1ow"),
    )


class TestScdType1Overwrite(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_inserts_new_rows(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all("SELECT id, name FROM customers ORDER BY id")
        assert rows == [(1, "Alice"), (2, "Bob")]

    async def test_updates_changed_rows(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        await t.run(RunRequest())
        await self.src.execute("UPDATE customers SET name = ? WHERE id = ?", ("Alicia", 1))
        with Tapestry() as t2:
            _make_knot(self.src, self.tgt)
        await t2.run(RunRequest())
        rows = await self.tgt.fetch_all("SELECT id, name FROM customers ORDER BY id")
        assert rows == [(1, "Alicia"), (2, "Bob")]

    async def test_upserted_count(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["rows_upserted"] == 2

    async def test_valid_construction(self) -> None:
        with Tapestry():
            scd = _make_knot(self.src, self.tgt)
        assert isinstance(scd, ScdType1Overwrite)


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
            ScdType1Overwrite(
                source_pool=self.src,
                source_query=q_knot,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                key_columns=_KEY_COLS,
                non_key_columns=_NON_KEY_COLS,
                _config=KnotConfig(id="scd1ow"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["scd1ow"]["rows_upserted"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> ScdType1Overwrite:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "key_columns": _KEY_COLS,
            "non_key_columns": _NON_KEY_COLS,
        }
        defaults.update(kwargs)
        with Tapestry():
            return ScdType1Overwrite(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: ScdType1Overwrite, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "key_columns": _KEY_COLS,
            "non_key_columns": _NON_KEY_COLS,
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

    async def test_rejects_overlap_key_and_non_key(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "overlap"):
            await self._call(k, key_columns=("id",), non_key_columns=("id", "name"))

    async def test_static_query_helpers(self) -> None:
        k = self._make_knot()
        assert "customers" in ScdType1Overwrite._select_existing_query(
            "customers", ("id",)
        )
        assert "UPDATE customers" in ScdType1Overwrite._update_query(
            "customers", ("id",), ("name",)
        )
        assert "INSERT INTO customers" in ScdType1Overwrite._insert_query(
            "customers", ("id", "name")
        )
        _ = k  # suppress unused warning
