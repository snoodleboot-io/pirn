"""Tests for :class:`BridgeTableBuilder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.dimensional.bridge_table_builder import (
    BridgeTableBuilder,
)
from pirn.tapestry import Tapestry

_SOURCE_QUERY = "SELECT account_sk, product_sk, group_id FROM account_product"
_BRIDGE_TABLE = "bridge_account_product"
_LEFT_KEY = ("account_sk",)
_RIGHT_KEY = ("product_sk",)
_GROUP_KEY = ("account_sk",)
_SOURCE_COLS = ("account_sk", "product_sk", "group_id")


async def _make_pools() -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute(
        "CREATE TABLE account_product ("
        "  account_sk INTEGER NOT NULL,"
        "  product_sk INTEGER NOT NULL,"
        "  group_id INTEGER NOT NULL"
        ")"
    )
    await src.execute_many(
        "INSERT INTO account_product (account_sk, product_sk, group_id) VALUES (?, ?, ?)",
        [(1, 10, 1), (1, 20, 1), (2, 30, 2)],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute(
        "CREATE TABLE bridge_account_product ("
        "  account_sk INTEGER NOT NULL,"
        "  product_sk INTEGER NOT NULL,"
        "  weight_factor REAL NOT NULL"
        ")"
    )
    return src, tgt


def _make_knot(src: SqlitePool, tgt: SqlitePool, **overrides: Any) -> BridgeTableBuilder:
    defaults: dict[str, Any] = {
        "source_pool": src,
        "source_query": _SOURCE_QUERY,
        "target_pool": tgt,
        "bridge_table": _BRIDGE_TABLE,
        "left_key_columns": _LEFT_KEY,
        "right_key_columns": _RIGHT_KEY,
        "weight_column": "weight_factor",
        "auto_weight": True,
        "group_key_columns": _GROUP_KEY,
        "source_columns": _SOURCE_COLS,
    }
    defaults.update(overrides)
    return BridgeTableBuilder(**defaults, _config=KnotConfig(id="bridge"))


class TestBridgeTableBuilder(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_auto_weight_proportional(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all(
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

    async def test_rebuilds_on_second_run(self) -> None:
        for _ in range(2):
            with Tapestry() as t:
                _make_knot(self.src, self.tgt)
            assert (await t.run(RunRequest())).succeeded
        count = await self.tgt.fetch_all("SELECT COUNT(*) FROM bridge_account_product")
        assert count[0][0] == 3

    async def test_manual_weight(self) -> None:
        src2 = SqlitePool(SqliteConfig(database=":memory:"))
        await src2.execute(
            "CREATE TABLE manual_src ("
            "  account_sk INTEGER NOT NULL,"
            "  product_sk INTEGER NOT NULL,"
            "  weight_factor REAL NOT NULL"
            ")"
        )
        await src2.execute_many(
            "INSERT INTO manual_src VALUES (?, ?, ?)",
            [(1, 10, 0.3), (1, 20, 0.7)],
        )
        with Tapestry() as t:
            _make_knot(
                src2,
                self.tgt,
                source_query="SELECT account_sk, product_sk, weight_factor FROM manual_src",
                auto_weight=False,
                group_key_columns=(),
                source_columns=("account_sk", "product_sk", "weight_factor"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all(
            "SELECT weight_factor FROM bridge_account_product ORDER BY product_sk"
        )
        assert abs(rows[0][0] - 0.3) < 1e-9
        assert abs(rows[1][0] - 0.7) < 1e-9
        await src2.close()

    async def test_result_tracks_rows_inserted(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["rows_inserted"] == 3


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
            BridgeTableBuilder(
                source_pool=self.src,
                source_query=q_knot,
                target_pool=self.tgt,
                bridge_table=_BRIDGE_TABLE,
                left_key_columns=_LEFT_KEY,
                right_key_columns=_RIGHT_KEY,
                weight_column="weight_factor",
                auto_weight=True,
                group_key_columns=_GROUP_KEY,
                source_columns=_SOURCE_COLS,
                _config=KnotConfig(id="bridge"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["bridge"]["rows_inserted"] == 3


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> BridgeTableBuilder:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "bridge_table": _BRIDGE_TABLE,
            "left_key_columns": _LEFT_KEY,
            "right_key_columns": _RIGHT_KEY,
            "weight_column": "weight_factor",
            "auto_weight": True,
            "group_key_columns": _GROUP_KEY,
            "source_columns": _SOURCE_COLS,
        }
        defaults.update(kwargs)
        with Tapestry():
            return BridgeTableBuilder(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: BridgeTableBuilder, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "bridge_table": _BRIDGE_TABLE,
            "left_key_columns": _LEFT_KEY,
            "right_key_columns": _RIGHT_KEY,
            "weight_column": "weight_factor",
            "auto_weight": True,
            "group_key_columns": _GROUP_KEY,
            "source_columns": _SOURCE_COLS,
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

    async def test_rejects_invalid_bridge_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, bridge_table="bad table")

    async def test_rejects_auto_weight_without_group_keys(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "group_key_columns"):
            await self._call(k, auto_weight=True, group_key_columns=())
