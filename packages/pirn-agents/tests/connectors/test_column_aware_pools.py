"""Tests for the column-aware core-pool subclasses (PIR-693).

``ColumnAwareSqlitePool`` / ``ColumnAwarePostgresPool`` reuse core's pooling and
its ``_reject_inline_interpolation`` injection guard, adding only column-aware
reads. Offline: an injected connection (sqlite) / pool (postgres) makes
``acquire`` return the double without opening a real backend.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.connectors.databases.sqlite_config import SqliteConfig

from pirn_agents.connectors.column_aware_postgres_pool import ColumnAwarePostgresPool
from pirn_agents.connectors.column_aware_sqlite_pool import ColumnAwareSqlitePool


class _FakeCursor:
    def __init__(self, columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
        self.description = [(name,) for name in columns]
        self._rows = rows
        self.closed = False

    async def fetchall(self) -> Sequence[Sequence[Any]]:
        return self._rows

    async def close(self) -> None:
        self.closed = True


class _FakeAiosqliteConnection:
    def __init__(self, columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
        self._columns = columns
        self._rows = rows
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, query: str, parameters: tuple[Any, ...]) -> _FakeCursor:
        self.calls.append((query, parameters))
        return _FakeCursor(self._columns, self._rows)

    async def close(self) -> None:
        return None


def _sqlite_pool(columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> ColumnAwareSqlitePool:
    conn = _FakeAiosqliteConnection(columns, rows)
    return ColumnAwareSqlitePool(SqliteConfig(database=":memory:"), connection=conn)  # pyright: ignore[reportCallIssue]


class TestColumnAwareSqlitePool:
    async def test_fetch_columns_returns_columns_and_rows(self) -> None:
        pool = _sqlite_pool(["id", "name"], [[1, "a"], [2, "b"]])
        columns, rows = await pool.fetch_columns("SELECT id, name FROM t")
        assert columns == ["id", "name"]
        assert rows == [[1, "a"], [2, "b"]]

    async def test_parameters_are_bound_not_interpolated(self) -> None:
        conn = _FakeAiosqliteConnection(["id"], [[1]])
        pool = ColumnAwareSqlitePool(SqliteConfig(database=":memory:"), connection=conn)  # pyright: ignore[reportCallIssue]
        await pool.fetch_columns("SELECT id FROM t WHERE id = ?", [42])
        assert conn.calls[0] == ("SELECT id FROM t WHERE id = ?", (42,))

    async def test_like_and_json_literals_are_accepted(self) -> None:
        # Regression (PIR-693): core's inline-interpolation guard rejects literal
        # % and {} — common in LLM-authored reads — so it is deliberately not
        # applied. LIKE '%term%' and JSON braces must pass through as data.
        conn = _FakeAiosqliteConnection(["n"], [["x"]])
        pool = ColumnAwareSqlitePool(SqliteConfig(database=":memory:"), connection=conn)  # pyright: ignore[reportCallIssue]
        await pool.fetch_columns("SELECT n FROM t WHERE n LIKE '%smith%'")
        await pool.fetch_columns("SELECT n FROM t WHERE j = '{\"k\": 1}'")
        assert [c[0] for c in conn.calls] == [
            "SELECT n FROM t WHERE n LIKE '%smith%'",
            "SELECT n FROM t WHERE j = '{\"k\": 1}'",
        ]


class _FakeRecord:
    def __init__(self, mapping: dict[str, Any]) -> None:
        self._mapping = mapping

    def keys(self) -> Sequence[str]:
        return list(self._mapping.keys())

    def values(self) -> Sequence[Any]:
        return list(self._mapping.values())


class _FakeAsyncpgPool:
    def __init__(self, records: Sequence[_FakeRecord]) -> None:
        self._records = records
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def acquire(self) -> Any:
        return self

    async def release(self, _connection: Any) -> None:
        return None

    async def fetch(self, query: str, *parameters: Any) -> Sequence[_FakeRecord]:
        self.calls.append((query, parameters))
        return self._records

    async def close(self) -> None:
        return None


class TestColumnAwarePostgresPool:
    async def test_fetch_columns_maps_records(self) -> None:
        records = [_FakeRecord({"id": 1, "name": "a"}), _FakeRecord({"id": 2, "name": "b"})]
        pool = ColumnAwarePostgresPool(pool=_FakeAsyncpgPool(records))
        columns, rows = await pool.fetch_columns("SELECT id, name FROM t WHERE id > $1", [0])
        assert columns == ["id", "name"]
        assert rows == [[1, "a"], [2, "b"]]

    async def test_empty_result_has_no_columns(self) -> None:
        pool = ColumnAwarePostgresPool(pool=_FakeAsyncpgPool([]))
        columns, rows = await pool.fetch_columns("SELECT id FROM t")
        assert columns == []
        assert rows == []

    async def test_like_literal_is_accepted(self) -> None:
        # Regression (PIR-693): '%s' in LIKE '%sale%' is data, not a bind marker.
        fake = _FakeAsyncpgPool([_FakeRecord({"n": "x"})])
        pool = ColumnAwarePostgresPool(pool=fake)
        await pool.fetch_columns("SELECT n FROM t WHERE n LIKE '%sale%'")
        assert fake.calls[0][0] == "SELECT n FROM t WHERE n LIKE '%sale%'"
