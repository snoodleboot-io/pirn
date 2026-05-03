"""``RefreshMaterializedView`` — issues REFRESH MATERIALIZED VIEW.

Wraps the vendor-specific SQL for Postgres (``REFRESH MATERIALIZED VIEW``)
and DuckDB (recreate from stored query). Supports Postgres and DuckDB
dialects.
"""

from __future__ import annotations

from typing import Any, Literal

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


_SUPPORTED_DIALECTS = frozenset({"postgres", "duckdb"})


class RefreshMaterializedView(SubTapestry):
    """Issue REFRESH MATERIALIZED VIEW (or equivalent) for a given view name."""

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        view_name: str,
        dialect: Literal["postgres", "duckdb"] = "postgres",
        concurrently: bool = False,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "RefreshMaterializedView: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(view_name, str) or not view_name:
            raise ValueError(
                "RefreshMaterializedView: view_name must be a non-empty string"
            )
        if dialect not in _SUPPORTED_DIALECTS:
            raise ValueError(
                f"RefreshMaterializedView: dialect must be one of "
                f"{sorted(_SUPPORTED_DIALECTS)!r}, got {dialect!r}"
            )
        IdentifierValidator.validate_column("view_name", view_name)
        self._pool = pool
        self._view_name = view_name
        self._dialect = dialect
        self._concurrently = concurrently
        super().__init__(_config=_config, **kwargs)

    @property
    def refresh_sql(self) -> str:
        if self._dialect == "postgres":
            concurrently_clause = " CONCURRENTLY" if self._concurrently else ""
            return (
                f"REFRESH MATERIALIZED VIEW{concurrently_clause} {self._view_name}"
            )
        return f"REFRESH {self._view_name}"

    async def process(self, **_: Any) -> dict[str, Any]:
        """Issue the vendor-specific REFRESH command for the materialized view.

        Returns:
            A dict with keys ``succeeded``, ``view_name``, and ``dialect``
            confirming the refresh was issued.
        """
        await self._pool.execute(self.refresh_sql)
        return {
            "succeeded": True,
            "view_name": self._view_name,
            "dialect": self._dialect,
        }
