"""Tests for :class:`ExposureLineageTag`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.analytics_engineering.exposure_lineage_tag import (
    ExposureLineageTag,
)
from pirn.tapestry import Tapestry

_SOURCE_TABLE = "stg_orders"
_TRANSFORM_KNOT_ID = "mart_knot_1"
_TARGET_TABLE = "mart_revenue"
_AUDIT_LOG_TABLE = "lineage_audit_log"

_CREATE_AUDIT_LOG = (
    "CREATE TABLE lineage_audit_log "
    "(source_table TEXT, transform_knot_id TEXT, target_table TEXT, recorded_at TEXT)"
)


async def _make_pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute(_CREATE_AUDIT_LOG)
    return p


def _make_knot(pool: SqlitePool) -> ExposureLineageTag:
    return ExposureLineageTag(
        pool=pool,
        source_table=_SOURCE_TABLE,
        transform_knot_id=_TRANSFORM_KNOT_ID,
        target_table=_TARGET_TABLE,
        _config=KnotConfig(id="lin"),
    )


class TestExposureLineageTag(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_inserts_lineage_record(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.pool.fetch_all(
            "SELECT source_table, transform_knot_id, target_table FROM lineage_audit_log"
        )
        assert rows == [(_SOURCE_TABLE, _TRANSFORM_KNOT_ID, _TARGET_TABLE)]

    async def test_returns_correct_keys(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool)
        result = await t.run(RunRequest())
        output = result.outputs[k.config.id]
        assert output["succeeded"] is True
        assert output["source_table"] == _SOURCE_TABLE
        assert output["transform_knot_id"] == _TRANSFORM_KNOT_ID
        assert output["target_table"] == _TARGET_TABLE
        assert "recorded_at" in output

    async def test_custom_audit_log_table(self) -> None:
        await self.pool.execute(
            "CREATE TABLE custom_log "
            "(source_table TEXT, transform_knot_id TEXT, target_table TEXT, recorded_at TEXT)"
        )
        with Tapestry() as t:
            ExposureLineageTag(
                pool=self.pool,
                source_table=_SOURCE_TABLE,
                transform_knot_id=_TRANSFORM_KNOT_ID,
                target_table=_TARGET_TABLE,
                audit_log_table="custom_log",
                _config=KnotConfig(id="lin2"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.pool.fetch_all("SELECT source_table FROM custom_log")
        assert rows == [(_SOURCE_TABLE,)]


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_source_table_from_upstream_knot(self) -> None:
        @knot
        async def emit_table() -> str:
            return _SOURCE_TABLE

        with Tapestry() as t:
            tbl_knot = emit_table(_config=KnotConfig(id="tbl"))
            ExposureLineageTag(
                pool=self.pool,
                source_table=tbl_knot,
                transform_knot_id=_TRANSFORM_KNOT_ID,
                target_table=_TARGET_TABLE,
                _config=KnotConfig(id="lin"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["lin"]["source_table"] == _SOURCE_TABLE


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> ExposureLineageTag:
        defaults: dict[str, Any] = {
            "pool": self.pool,
            "source_table": _SOURCE_TABLE,
            "transform_knot_id": _TRANSFORM_KNOT_ID,
            "target_table": _TARGET_TABLE,
        }
        defaults.update(kwargs)
        with Tapestry():
            return ExposureLineageTag(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: ExposureLineageTag, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "pool": self.pool,
            "source_table": _SOURCE_TABLE,
            "transform_knot_id": _TRANSFORM_KNOT_ID,
            "target_table": _TARGET_TABLE,
            "audit_log_table": _AUDIT_LOG_TABLE,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, pool="bad")

    async def test_rejects_empty_source_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_table"):
            await self._call(k, source_table="")

    async def test_rejects_empty_target_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "target_table"):
            await self._call(k, target_table="")

    async def test_rejects_invalid_identifier(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, source_table="src table")
