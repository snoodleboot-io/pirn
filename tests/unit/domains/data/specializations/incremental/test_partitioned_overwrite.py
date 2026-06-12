"""Tests for :class:`PartitionedOverwrite`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.incremental.partitioned_overwrite import PartitionedOverwrite
from pirn.tapestry import Tapestry

_SRC_QUERY = (
    "SELECT event_date, metric, value FROM facts "
    "WHERE event_date = '2024-01-01'"
)
_TARGET_TABLE = "facts"
_PARTITION_COL = "event_date"
_PARTITION_VAL = "2024-01-01"
_SRC_COLS = ("event_date", "metric", "value")


async def _make_pools() -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute(
        "CREATE TABLE facts (event_date TEXT NOT NULL, metric TEXT NOT NULL, value REAL NOT NULL)"
    )
    await src.execute_many(
        "INSERT INTO facts (event_date, metric, value) VALUES (?, ?, ?)",
        [("2024-01-01", "clicks", 999.0), ("2024-01-01", "views", 888.0)],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute(
        "CREATE TABLE facts (event_date TEXT NOT NULL, metric TEXT NOT NULL, value REAL NOT NULL)"
    )
    await tgt.execute_many(
        "INSERT INTO facts (event_date, metric, value) VALUES (?, ?, ?)",
        [
            ("2024-01-01", "clicks", 100.0),
            ("2024-01-01", "views", 200.0),
            ("2024-01-02", "clicks", 50.0),
        ],
    )
    return src, tgt


class TestPartitionedOverwrite(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_overwrites_only_target_partition(self) -> None:
        with Tapestry() as t:
            PartitionedOverwrite(
                source_pool=self.src,
                source_query=_SRC_QUERY,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                partition_column=_PARTITION_COL,
                partition_value=_PARTITION_VAL,
                source_columns=_SRC_COLS,
                _config=KnotConfig(id="po"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        partition_rows = await self.tgt.fetch_all(
            "SELECT metric, value FROM facts WHERE event_date = '2024-01-01' ORDER BY metric"
        )
        assert set(r[0] for r in partition_rows) == {"clicks", "views"}
        assert any(abs(r[1] - 999.0) < 0.01 for r in partition_rows if r[0] == "clicks")
        other_rows = await self.tgt.fetch_all(
            "SELECT metric FROM facts WHERE event_date = '2024-01-02'"
        )
        assert len(other_rows) == 1

    async def test_result_contains_rows_inserted(self) -> None:
        with Tapestry() as t:
            k = PartitionedOverwrite(
                source_pool=self.src,
                source_query=_SRC_QUERY,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                partition_column=_PARTITION_COL,
                partition_value=_PARTITION_VAL,
                source_columns=_SRC_COLS,
                _config=KnotConfig(id="po"),
            )
        result = await t.run(RunRequest())
        assert result.outputs[k.config.id]["rows_inserted"] == 2


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_source_query_from_upstream_knot(self) -> None:
        @knot
        async def emit_query() -> str:
            return _SRC_QUERY

        with Tapestry() as t:
            q_knot = emit_query(_config=KnotConfig(id="q"))
            PartitionedOverwrite(
                source_pool=self.src,
                source_query=q_knot,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                partition_column=_PARTITION_COL,
                partition_value=_PARTITION_VAL,
                source_columns=_SRC_COLS,
                _config=KnotConfig(id="po"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["po"]["rows_inserted"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> PartitionedOverwrite:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SRC_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "partition_column": _PARTITION_COL,
            "partition_value": _PARTITION_VAL,
            "source_columns": _SRC_COLS,
        }
        defaults.update(kwargs)
        with Tapestry():
            return PartitionedOverwrite(**defaults, _config=KnotConfig(id="po"))

    async def _call(self, k: PartitionedOverwrite, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SRC_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "partition_column": _PARTITION_COL,
            "partition_value": _PARTITION_VAL,
            "source_columns": _SRC_COLS,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool_source(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, source_pool="bad")

    async def test_rejects_invalid_partition_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, partition_column="event date")

    async def test_rejects_empty_source_query(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_query"):
            await self._call(k, source_query="")
