"""Tests for :class:`GeoEnricher`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.feature_engineering.geo_enricher import (
    GeoEnricher,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE user_locations (user_id INTEGER, lat REAL, lon REAL)"
        )
        await p.execute(
            "CREATE TABLE geo_lookup "
            "(lat_min REAL, lat_max REAL, lon_min REAL, lon_max REAL, "
            "country TEXT, region TEXT, timezone TEXT)"
        )
        await p.execute(
            "CREATE TABLE enriched_locations "
            "(user_id INTEGER, lat REAL, lon REAL, "
            "country TEXT, region TEXT, timezone TEXT)"
        )
        await p.execute_many(
            "INSERT INTO user_locations VALUES (?, ?, ?)",
            [(1, 51.5, -0.1), (2, 40.7, -74.0)],
        )
        await p.execute_many(
            "INSERT INTO geo_lookup VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (50.0, 60.0, -5.0, 5.0, "GB", "England", "Europe/London"),
                (40.0, 45.0, -80.0, -70.0, "US", "New York", "America/New_York"),
            ],
        )
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        
    def test_rejects_non_pool(self) -> None:
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            GeoEnricher(
                pool="bad",  # type: ignore[arg-type]
                source_table="user_locations",
                target_table="enriched_locations",
                lookup_table="geo_lookup",
                lat_column="lat",
                lon_column="lon",
                _config=KnotConfig(id="geo"),
            )

    def test_rejects_missing_lat_and_ip(self) -> None:
        pool = self.pool
        with self.assertRaisesRegex(ValueError, "lat_column"):
            GeoEnricher(
                pool=pool,
                source_table="user_locations",
                target_table="enriched_locations",
                lookup_table="geo_lookup",
                _config=KnotConfig(id="geo"),
            )

    def test_rejects_lat_without_lon(self) -> None:
        pool = self.pool
        with self.assertRaisesRegex(ValueError, "lon_column"):
            GeoEnricher(
                pool=pool,
                source_table="user_locations",
                target_table="enriched_locations",
                lookup_table="geo_lookup",
                lat_column="lat",
                _config=KnotConfig(id="geo"),
            )


class TestBehaviour(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        await p.execute(
            "CREATE TABLE user_locations (user_id INTEGER, lat REAL, lon REAL)"
        )
        await p.execute(
            "CREATE TABLE geo_lookup "
            "(lat_min REAL, lat_max REAL, lon_min REAL, lon_max REAL, "
            "country TEXT, region TEXT, timezone TEXT)"
        )
        await p.execute(
            "CREATE TABLE enriched_locations "
            "(user_id INTEGER, lat REAL, lon REAL, "
            "country TEXT, region TEXT, timezone TEXT)"
        )
        await p.execute_many(
            "INSERT INTO user_locations VALUES (?, ?, ?)",
            [(1, 51.5, -0.1), (2, 40.7, -74.0)],
        )
        await p.execute_many(
            "INSERT INTO geo_lookup VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (50.0, 60.0, -5.0, 5.0, "GB", "England", "Europe/London"),
                (40.0, 45.0, -80.0, -70.0, "US", "New York", "America/New_York"),
            ],
        )
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        
    async def test_enriches_rows_with_lat_lon(self) -> None:
        pool = self.pool
        with Tapestry() as t:
            GeoEnricher(
                pool=pool,
                source_table="user_locations",
                target_table="enriched_locations",
                lookup_table="geo_lookup",
                lat_column="lat",
                lon_column="lon",
                _config=KnotConfig(id="geo"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["geo"]
        assert output["rows_enriched"] == 2
        rows = await pool.fetch_all(
            "SELECT user_id, country FROM enriched_locations ORDER BY user_id"
        )
        assert rows == [(1, "GB"), (2, "US")]
