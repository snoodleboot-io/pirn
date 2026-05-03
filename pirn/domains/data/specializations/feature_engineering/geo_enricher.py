"""``GeoEnricher`` — enriches rows with geographic metadata from a lookup table.

Looks up country, region, and timezone from a local in-database lookup
table keyed on lat/lon ranges or IP prefix. No external API calls are
made.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class GeoEnricher(SubTapestry):
    """Enrich rows with geographic metadata from a local lookup table."""

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        source_table: str,
        target_table: str,
        lookup_table: str,
        lat_column: str = "",
        lon_column: str = "",
        ip_column: str = "",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "GeoEnricher: pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_table", source_table),
            ("target_table", target_table),
            ("lookup_table", lookup_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"GeoEnricher: {label} must be a non-empty string"
                )
        if not lat_column and not ip_column:
            raise ValueError(
                "GeoEnricher: must supply lat_column/lon_column or ip_column"
            )
        if lat_column and not lon_column:
            raise ValueError(
                "GeoEnricher: lat_column requires lon_column"
            )
        IdentifierValidator.validate_column("source_table", source_table)
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("lookup_table", lookup_table)
        if lat_column:
            IdentifierValidator.validate_column("lat_column", lat_column)
            IdentifierValidator.validate_column("lon_column", lon_column)
        if ip_column:
            IdentifierValidator.validate_column("ip_column", ip_column)
        self._pool = pool
        self._source_table = source_table
        self._target_table = target_table
        self._lookup_table = lookup_table
        self._lat_column = lat_column
        self._lon_column = lon_column
        self._ip_column = ip_column
        super().__init__(_config=_config, **kwargs)

    def _build_enrich_query(self) -> str:
        if self._lat_column:
            return (
                f"SELECT s.*, l.country, l.region, l.timezone "
                f"FROM {self._source_table} s "
                f"LEFT JOIN {self._lookup_table} l "
                f"ON s.{self._lat_column} BETWEEN l.lat_min AND l.lat_max "
                f"AND s.{self._lon_column} BETWEEN l.lon_min AND l.lon_max"
            )
        return (
            f"SELECT s.*, l.country, l.region, l.timezone "
            f"FROM {self._source_table} s "
            f"LEFT JOIN {self._lookup_table} l "
            f"ON s.{self._ip_column} LIKE l.ip_prefix || '%'"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Enrich source rows with geographic metadata and write to target table.

        Returns:
            A dict with keys ``succeeded``, ``target_table``, and
            ``rows_enriched`` summarising the enrichment run.
        """
        rows = await self._pool.fetch_all(self._build_enrich_query())
        if not rows:
            return {
                "succeeded": True,
                "target_table": self._target_table,
                "rows_enriched": 0,
            }
        col_count = len(rows[0])
        placeholders = ", ".join(["?"] * col_count)
        insert_sql = (
            f"INSERT INTO {self._target_table} VALUES ({placeholders})"
        )
        rows_enriched = 0
        for row in rows:
            await self._pool.execute(insert_sql, tuple(row))
            rows_enriched += 1
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_enriched": rows_enriched,
        }
