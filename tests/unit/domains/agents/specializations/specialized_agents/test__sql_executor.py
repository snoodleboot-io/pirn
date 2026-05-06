"""Unit tests for :class:`_SQLExecutor`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.specialized_agents._sql_executor import (
    _SQLExecutor,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubDatabaseConnectionPool,
)


class _SqlSource(Knot):
    def __init__(self, sql, *, _config, **kwargs):
        self._sql = sql
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any):
        return self._sql


class TestSQLExecutorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_executes_query_and_returns_rows(self) -> None:
        pool = StubDatabaseConnectionPool(rows=[(1, "Alice"), (2, "Bob")])
        with Tapestry() as t:
            src = _SqlSource("SELECT id, name FROM users", _config=KnotConfig(id="sql"))
            _SQLExecutor(sql=src, pool=pool, _config=KnotConfig(id="ex"))
        result = await t.run(RunRequest())
        rows = result.outputs["ex"]
        assert rows == [(1, "Alice"), (2, "Bob")]

    async def test_rejects_empty_sql(self) -> None:
        pool = StubDatabaseConnectionPool()
        with Tapestry() as t:
            src = _SqlSource("", _config=KnotConfig(id="sql"))
            _SQLExecutor(sql=src, pool=pool, _config=KnotConfig(id="ex"))
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_rejects_inline_interpolation(self) -> None:
        pool = StubDatabaseConnectionPool()
        with Tapestry() as t:
            src = _SqlSource("SELECT * FROM t WHERE x = {value}", _config=KnotConfig(id="sql"))
            _SQLExecutor(sql=src, pool=pool, _config=KnotConfig(id="ex"))
        result = await t.run(RunRequest())
        assert not result.succeeded


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_empty_sql(self) -> None:
        pool = StubDatabaseConnectionPool()
        with Tapestry():
            k = _SQLExecutor.__new__(_SQLExecutor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises(ValueError):
            await k.process(sql="", pool=pool)
