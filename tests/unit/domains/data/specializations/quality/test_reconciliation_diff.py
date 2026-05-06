"""Tests for :class:`ReconciliationDiff`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.quality.reconciliation_diff import ReconciliationDiff
from pirn.tapestry import Tapestry

_SRC_QUERY = "SELECT id, value FROM records ORDER BY id"
_TGT_QUERY = "SELECT id, value FROM records ORDER BY id"
_KEY_COLS = ("id",)
_VAL_COLS = ("value",)


async def _make_source_pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE records (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
    )
    await p.execute_many(
        "INSERT INTO records (id, value) VALUES (?, ?)",
        [(1, "alpha"), (2, "beta"), (3, "gamma")],
    )
    return p


async def _make_target_pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(
        "CREATE TABLE records (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
    )
    await p.execute_many(
        "INSERT INTO records (id, value) VALUES (?, ?)",
        [(1, "alpha"), (2, "CHANGED"), (4, "delta")],
    )
    return p


def _make_knot(src: SqlitePool, tgt: SqlitePool) -> ReconciliationDiff:
    return ReconciliationDiff(
        source_pool=src,
        source_query=_SRC_QUERY,
        target_pool=tgt,
        target_query=_TGT_QUERY,
        key_columns=_KEY_COLS,
        value_columns=_VAL_COLS,
        _config=KnotConfig(id="diff"),
    )


class TestReconciliationDiff(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src = await _make_source_pool()
        self.tgt = await _make_target_pool()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_classifies_added_removed_changed_matched(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs[k.config.id]
        assert [3] in out["added"]
        assert [4] in out["removed"]
        assert [2] in out["changed"]
        assert out["matched"] == 1
        assert out["total_differences"] == 3

    async def test_identical_tables_have_no_differences(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.src, self.src)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["total_differences"] == 0
        assert out["matched"] == 3

    async def test_result_has_succeeded_true(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.outputs[k.config.id]["succeeded"] is True


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src = await _make_source_pool()
        self.tgt = await _make_target_pool()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_source_query_from_upstream_knot(self) -> None:
        @knot
        async def emit_query() -> str:
            return _SRC_QUERY

        with Tapestry() as t:
            q_knot = emit_query(_config=KnotConfig(id="q"))
            ReconciliationDiff(
                source_pool=self.src,
                source_query=q_knot,
                target_pool=self.tgt,
                target_query=_TGT_QUERY,
                key_columns=_KEY_COLS,
                value_columns=_VAL_COLS,
                _config=KnotConfig(id="diff"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["diff"]["total_differences"] == 3


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src = await _make_source_pool()
        self.tgt = await _make_target_pool()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> ReconciliationDiff:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SRC_QUERY,
            "target_pool": self.tgt,
            "target_query": _TGT_QUERY,
            "key_columns": _KEY_COLS,
            "value_columns": _VAL_COLS,
        }
        defaults.update(kwargs)
        with Tapestry():
            return ReconciliationDiff(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: ReconciliationDiff, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SRC_QUERY,
            "target_pool": self.tgt,
            "target_query": _TGT_QUERY,
            "key_columns": _KEY_COLS,
            "value_columns": _VAL_COLS,
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

    async def test_rejects_overlapping_columns(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "overlap"):
            await self._call(k, key_columns=("id", "value"), value_columns=("value",))
