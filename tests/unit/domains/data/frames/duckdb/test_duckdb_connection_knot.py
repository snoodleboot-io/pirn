"""Tests for :class:`DuckDBConnectionKnot`."""

from __future__ import annotations

import unittest

try:
    import duckdb  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("duckdb not installed") from _e

from pirn.core.knot_config import KnotConfig
from pirn_data.frames.duckdb.duckdb_connection import DuckDBConnection
from pirn_data.frames.duckdb.duckdb_connection_knot import DuckDBConnectionKnot


class TestDuckDBConnectionKnot(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> DuckDBConnectionKnot:
        return DuckDBConnectionKnot(_config=KnotConfig(id="test-conn"))

    async def test_process_returns_duckdb_connection(self) -> None:
        knot = self._make_knot()
        result = await knot.process()
        assert isinstance(result, DuckDBConnection)

    async def test_process_connection_is_usable(self) -> None:
        knot = self._make_knot()
        wrapper = await knot.process()
        rows = wrapper.conn.execute("SELECT 42 AS answer").fetchall()
        assert rows == [(42,)]

    async def test_process_returns_fresh_connection_each_call(self) -> None:
        knot = self._make_knot()
        first = await knot.process()
        second = await knot.process()
        assert first is not second
