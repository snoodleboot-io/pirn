"""Tests for :class:`RefreshMaterializedView`."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.specializations.analytics_engineering.refresh_materialized_view import (
    RefreshMaterializedView,
)
from pirn.tapestry import Tapestry


class StubPool(DatabaseConnectionPool):
    def __init__(self) -> None:
        self.executed: list[str] = []

    async def execute(self, sql: str, *args: object) -> None:
        self.executed.append(sql)


class TestConstruction:
    def test_rejects_non_pool(self) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            RefreshMaterializedView(
                pool="bad",  # type: ignore[arg-type]
                view_name="my_view",
                _config=KnotConfig(id="rv"),
            )

    def test_rejects_empty_view_name(self) -> None:
        pool = StubPool()
        with pytest.raises(ValueError, match="view_name"):
            RefreshMaterializedView(
                pool=pool,
                view_name="",
                _config=KnotConfig(id="rv"),
            )

    def test_rejects_unsupported_dialect(self) -> None:
        pool = StubPool()
        with pytest.raises(ValueError, match="dialect"):
            RefreshMaterializedView(
                pool=pool,
                view_name="my_view",
                dialect="mysql",  # type: ignore[arg-type]
                _config=KnotConfig(id="rv"),
            )

    def test_rejects_invalid_identifier(self) -> None:
        pool = StubPool()
        with pytest.raises(ValueError, match="plain identifier"):
            RefreshMaterializedView(
                pool=pool,
                view_name="my view",
                _config=KnotConfig(id="rv"),
            )


class TestRefreshSql:
    def test_postgres_sql(self) -> None:
        pool = StubPool()
        k = RefreshMaterializedView(
            pool=pool,
            view_name="my_view",
            dialect="postgres",
            _config=KnotConfig(id="rv"),
        )
        assert k.refresh_sql == "REFRESH MATERIALIZED VIEW my_view"

    def test_postgres_concurrently(self) -> None:
        pool = StubPool()
        k = RefreshMaterializedView(
            pool=pool,
            view_name="my_view",
            dialect="postgres",
            concurrently=True,
            _config=KnotConfig(id="rv"),
        )
        assert k.refresh_sql == "REFRESH MATERIALIZED VIEW CONCURRENTLY my_view"

    def test_duckdb_sql(self) -> None:
        pool = StubPool()
        k = RefreshMaterializedView(
            pool=pool,
            view_name="my_view",
            dialect="duckdb",
            _config=KnotConfig(id="rv"),
        )
        assert k.refresh_sql == "REFRESH my_view"


@pytest.mark.asyncio
class TestBehaviour:
    async def test_issues_refresh_and_returns_dict(self) -> None:
        pool = StubPool()
        with Tapestry() as t:
            RefreshMaterializedView(
                pool=pool,
                view_name="revenue_mv",
                dialect="postgres",
                _config=KnotConfig(id="rv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert any("REFRESH" in sql for sql in pool.executed)
