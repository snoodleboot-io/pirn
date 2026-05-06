"""Tests for :class:`GeoEnricher`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.feature_engineering.geo_enricher import GeoEnricher
from pirn.tapestry import Tapestry


async def _make_pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute("CREATE TABLE user_locations (user_id INTEGER, lat REAL, lon REAL)")
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
    return p


def _make_knot(pool: SqlitePool, **overrides: Any) -> GeoEnricher:
    defaults: dict[str, Any] = {
        "pool": pool,
        "source_table": "user_locations",
        "target_table": "enriched_locations",
        "lookup_table": "geo_lookup",
        "lat_column": "lat",
        "lon_column": "lon",
        "ip_column": "",
    }
    defaults.update(overrides)
    return GeoEnricher(**defaults, _config=KnotConfig(id="geo"))


class TestGeoEnricher(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_enriches_rows_with_lat_lon(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["geo"]
        assert output["rows_enriched"] == 2
        rows = await self.pool.fetch_all(
            "SELECT user_id, country FROM enriched_locations ORDER BY user_id"
        )
        assert rows == [(1, "GB"), (2, "US")]

    async def test_result_tracks_target_table(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.outputs[k.config.id]["target_table"] == "enriched_locations"


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_target_table_from_upstream_knot(self) -> None:
        @knot
        async def emit_table() -> str:
            return "enriched_locations"

        with Tapestry() as t:
            tbl_knot = emit_table(_config=KnotConfig(id="tbl"))
            GeoEnricher(
                pool=self.pool,
                source_table="user_locations",
                target_table=tbl_knot,
                lookup_table="geo_lookup",
                lat_column="lat",
                lon_column="lon",
                ip_column="",
                _config=KnotConfig(id="geo"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["geo"]["rows_enriched"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> GeoEnricher:
        defaults: dict[str, Any] = {
            "pool": self.pool,
            "source_table": "user_locations",
            "target_table": "enriched_locations",
            "lookup_table": "geo_lookup",
            "lat_column": "lat",
            "lon_column": "lon",
            "ip_column": "",
        }
        defaults.update(kwargs)
        with Tapestry():
            return GeoEnricher(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: GeoEnricher, **overrides: Any) -> Any:
        args: dict[str, Any] = {
            "pool": self.pool,
            "source_table": "user_locations",
            "target_table": "enriched_locations",
            "lookup_table": "geo_lookup",
            "lat_column": "lat",
            "lon_column": "lon",
            "ip_column": "",
        }
        args.update(overrides)
        return await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, pool="bad")

    async def test_rejects_missing_lat_and_ip(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "lat_column"):
            await self._call(k, lat_column="", ip_column="")

    async def test_rejects_lat_without_lon(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "lon_column"):
            await self._call(k, lat_column="lat", lon_column="")
