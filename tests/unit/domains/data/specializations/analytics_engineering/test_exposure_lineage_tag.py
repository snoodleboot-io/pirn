"""Tests for :class:`ExposureLineageTag`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.analytics_engineering.exposure_lineage_tag import (
    ExposureLineageTag,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE lineage_audit_log "
            "(source_table TEXT, transform_knot_id TEXT, "
            "target_table TEXT, recorded_at TEXT)"
        )
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        
    def test_rejects_non_pool(self) -> None:
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            ExposureLineageTag(
                pool="bad",  # type: ignore[arg-type]
                source_table="src",
                transform_knot_id="t1",
                target_table="tgt",
                _config=KnotConfig(id="lin"),
            )

    def test_rejects_empty_source_table(self) -> None:
        pool = self.pool
        with self.assertRaisesRegex(ValueError, "source_table"):
            ExposureLineageTag(
                pool=pool,
                source_table="",
                transform_knot_id="t1",
                target_table="tgt",
                _config=KnotConfig(id="lin"),
            )

    def test_rejects_invalid_identifier(self) -> None:
        pool = self.pool
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            ExposureLineageTag(
                pool=pool,
                source_table="src table",
                transform_knot_id="t1",
                target_table="tgt",
                _config=KnotConfig(id="lin"),
            )


class TestBehaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE lineage_audit_log "
            "(source_table TEXT, transform_knot_id TEXT, "
            "target_table TEXT, recorded_at TEXT)"
        )
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        
    async def test_inserts_lineage_record(self) -> None:
        pool = self.pool
        with Tapestry() as t:
            ExposureLineageTag(
                pool=pool,
                source_table="stg_orders",
                transform_knot_id="mart_knot_1",
                target_table="mart_revenue",
                _config=KnotConfig(id="lin"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await pool.fetch_all(
            "SELECT source_table, transform_knot_id, target_table "
            "FROM lineage_audit_log"
        )
        assert rows == [("stg_orders", "mart_knot_1", "mart_revenue")]

    async def test_returns_correct_keys(self) -> None:
        pool = self.pool
        with Tapestry() as t:
            ExposureLineageTag(
                pool=pool,
                source_table="stg_orders",
                transform_knot_id="mart_knot_1",
                target_table="mart_revenue",
                _config=KnotConfig(id="lin2"),
            )
        result = await t.run(RunRequest())
        output = result.outputs["lin2"]
        assert output["source_table"] == "stg_orders"
        assert output["transform_knot_id"] == "mart_knot_1"
        assert output["target_table"] == "mart_revenue"
        assert "recorded_at" in output
