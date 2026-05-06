"""``GeoEnricher`` — enrich rows with geographic metadata from a lookup table.

Looks up country, region, and timezone from a local in-database lookup
table keyed on lat/lon ranges or IP prefix. No external API calls are
made.

Algorithm:
    1. Receive resolved ``pool``, ``source_table``, ``target_table``,
       ``lookup_table``, ``lat_column``, ``lon_column``, and ``ip_column``
       in ``process()``.
    2. Validate pool type, table identifiers, and column mode consistency
       (must supply lat/lon pair or ip column).
    3. Build and execute a LEFT JOIN query from ``source_table`` to
       ``lookup_table``.
    4. Insert enriched rows into ``target_table``.
    5. Return a summary dict with ``succeeded``, ``target_table``, and
       ``rows_enriched``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.identifier_validator import IdentifierValidator


class GeoEnricher(Knot):
    """Enrich rows with geographic metadata from a local lookup table."""

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        source_table: Knot | str,
        target_table: Knot | str,
        lookup_table: Knot | str,
        lat_column: Knot | str,
        lon_column: Knot | str,
        ip_column: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            source_table=source_table,
            target_table=target_table,
            lookup_table=lookup_table,
            lat_column=lat_column,
            lon_column=lon_column,
            ip_column=ip_column,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _build_enrich_query(
        source_table: str,
        lookup_table: str,
        lat_column: str,
        lon_column: str,
        ip_column: str,
    ) -> str:
        if lat_column:
            return (
                f"SELECT s.*, l.country, l.region, l.timezone "
                f"FROM {source_table} s "
                f"LEFT JOIN {lookup_table} l "
                f"ON s.{lat_column} BETWEEN l.lat_min AND l.lat_max "
                f"AND s.{lon_column} BETWEEN l.lon_min AND l.lon_max"
            )
        return (
            f"SELECT s.*, l.country, l.region, l.timezone "
            f"FROM {source_table} s "
            f"LEFT JOIN {lookup_table} l "
            f"ON s.{ip_column} LIKE l.ip_prefix || '%'"
        )

    async def process(
        self,
        *,
        pool: Any,
        source_table: Any,
        target_table: Any,
        lookup_table: Any,
        lat_column: Any,
        lon_column: Any,
        ip_column: Any,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("GeoEnricher: pool must be a DatabaseConnectionPool")
        for label, value in (
            ("source_table", source_table),
            ("target_table", target_table),
            ("lookup_table", lookup_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"GeoEnricher: {label} must be a non-empty string")
        if not lat_column and not ip_column:
            raise ValueError("GeoEnricher: must supply lat_column/lon_column or ip_column")
        if lat_column and not lon_column:
            raise ValueError("GeoEnricher: lat_column requires lon_column")
        IdentifierValidator.validate_column("source_table", source_table)
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("lookup_table", lookup_table)
        if lat_column:
            IdentifierValidator.validate_column("lat_column", lat_column)
            IdentifierValidator.validate_column("lon_column", lon_column)
        if ip_column:
            IdentifierValidator.validate_column("ip_column", ip_column)
        rows = await pool.fetch_all(
            self._build_enrich_query(source_table, lookup_table, lat_column, lon_column, ip_column)
        )
        if not rows:
            return {
                "succeeded": True,
                "target_table": target_table,
                "rows_enriched": 0,
            }
        col_count = len(rows[0])
        placeholders = ", ".join(["?"] * col_count)
        insert_sql = f"INSERT INTO {target_table} VALUES ({placeholders})"
        rows_enriched = 0
        for row in rows:
            await pool.execute(insert_sql, tuple(row))
            rows_enriched += 1
        return {
            "succeeded": True,
            "target_table": target_table,
            "rows_enriched": rows_enriched,
        }
