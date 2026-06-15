"""``RefreshMaterializedView`` — issues REFRESH MATERIALIZED VIEW.

Wraps the vendor-specific SQL for Postgres (``REFRESH MATERIALIZED VIEW``)
and DuckDB (recreate from stored query). Supports Postgres and DuckDB
dialects.

Algorithm:
    1. Receive resolved ``pool``, ``view_name``, ``dialect``, and
       ``concurrently`` in ``process()``.
    2. Validate all inputs: pool type, non-empty view_name, allowed dialect,
       and identifier safety.
    3. Build the vendor-specific REFRESH SQL statement.
    4. Execute the statement via ``pool``.
    5. Return a summary dict with ``succeeded``, ``view_name``, and
       ``dialect``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
    [3] PostgreSQL — REFRESH MATERIALIZED VIEW:
        https://www.postgresql.org/docs/current/sql-refreshmaterializedview.html
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.identifier_validator import IdentifierValidator


class RefreshMaterializedView(Knot):
    """Issue REFRESH MATERIALIZED VIEW (or equivalent) for a given view name."""

    _supported_dialects: ClassVar[frozenset[str]] = frozenset({"postgres", "duckdb"})

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        view_name: Knot | str,
        dialect: Knot | str = "postgres",
        concurrently: Knot | bool = False,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            view_name=view_name,
            dialect=dialect,
            concurrently=concurrently,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _refresh_sql(view_name: str, dialect: str, concurrently: bool) -> str:
        if dialect == "postgres":
            concurrently_clause = " CONCURRENTLY" if concurrently else ""
            return f"REFRESH MATERIALIZED VIEW{concurrently_clause} {view_name}"
        return f"REFRESH {view_name}"

    async def process(
        self,
        *,
        pool: Any,
        view_name: Any,
        dialect: Any = "postgres",
        concurrently: Any = False,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("RefreshMaterializedView: pool must be a DatabaseConnectionPool")
        if not isinstance(view_name, str) or not view_name:
            raise ValueError("RefreshMaterializedView: view_name must be a non-empty string")
        if dialect not in self._supported_dialects:
            raise ValueError(
                f"RefreshMaterializedView: dialect must be one of "
                f"{sorted(self._supported_dialects)!r}, got {dialect!r}"
            )
        IdentifierValidator.validate_column("view_name", view_name)
        await pool.execute(
            RefreshMaterializedView._refresh_sql(view_name, dialect, bool(concurrently))
        )
        return {
            "succeeded": True,
            "view_name": view_name,
            "dialect": dialect,
        }
