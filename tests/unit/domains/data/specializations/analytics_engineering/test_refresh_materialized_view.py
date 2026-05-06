"""Tests for :class:`RefreshMaterializedView`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.specializations.analytics_engineering.refresh_materialized_view import (
    RefreshMaterializedView,
)
from pirn.tapestry import Tapestry

_VIEW_NAME = "revenue_mv"
_DIALECT = "postgres"


class StubPool(DatabaseConnectionPool):
    def __init__(self) -> None:
        self.executed: list[str] = []

    async def execute(self, sql: str, *args: object) -> None:
        self.executed.append(sql)


def _make_knot(pool: StubPool) -> RefreshMaterializedView:
    return RefreshMaterializedView(
        pool=pool,
        view_name=_VIEW_NAME,
        dialect=_DIALECT,
        _config=KnotConfig(id="rv"),
    )


class TestRefreshMaterializedView(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.pool = StubPool()

    async def test_issues_refresh_and_returns_dict(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        assert any("REFRESH" in sql for sql in self.pool.executed)

    async def test_postgres_sql(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool)
        await t.run(RunRequest())
        assert self.pool.executed[-1] == f"REFRESH MATERIALIZED VIEW {_VIEW_NAME}"

    async def test_postgres_concurrently(self) -> None:
        with Tapestry() as t:
            RefreshMaterializedView(
                pool=self.pool,
                view_name=_VIEW_NAME,
                dialect="postgres",
                concurrently=True,
                _config=KnotConfig(id="rv"),
            )
        await t.run(RunRequest())
        assert self.pool.executed[-1] == f"REFRESH MATERIALIZED VIEW CONCURRENTLY {_VIEW_NAME}"

    async def test_duckdb_sql(self) -> None:
        with Tapestry() as t:
            RefreshMaterializedView(
                pool=self.pool,
                view_name=_VIEW_NAME,
                dialect="duckdb",
                _config=KnotConfig(id="rv"),
            )
        await t.run(RunRequest())
        assert self.pool.executed[-1] == f"REFRESH {_VIEW_NAME}"

    async def test_returns_correct_keys(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool)
        result = await t.run(RunRequest())
        output = result.outputs[k.config.id]
        assert output["succeeded"] is True
        assert output["view_name"] == _VIEW_NAME
        assert output["dialect"] == _DIALECT


class TestWiring(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.pool = StubPool()

    async def test_view_name_from_upstream_knot(self) -> None:
        @knot
        async def emit_view() -> str:
            return _VIEW_NAME

        with Tapestry() as t:
            view_knot = emit_view(_config=KnotConfig(id="vn"))
            RefreshMaterializedView(
                pool=self.pool,
                view_name=view_knot,
                dialect=_DIALECT,
                _config=KnotConfig(id="rv"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["rv"]["view_name"] == _VIEW_NAME


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.pool = StubPool()

    def _make_knot(self, **kwargs: Any) -> RefreshMaterializedView:
        defaults: dict[str, Any] = {
            "pool": self.pool,
            "view_name": _VIEW_NAME,
            "dialect": _DIALECT,
        }
        defaults.update(kwargs)
        with Tapestry():
            return RefreshMaterializedView(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: RefreshMaterializedView, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "pool": self.pool,
            "view_name": _VIEW_NAME,
            "dialect": _DIALECT,
            "concurrently": False,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, pool="bad")

    async def test_rejects_empty_view_name(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "view_name"):
            await self._call(k, view_name="")

    async def test_rejects_unsupported_dialect(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "dialect"):
            await self._call(k, dialect="mysql")

    async def test_rejects_invalid_identifier(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, view_name="my view")
