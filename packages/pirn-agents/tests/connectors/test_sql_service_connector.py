"""Mirrored tests for :class:`SqlServiceConnector` with offline DB doubles (F16-S2).

No real database driver is used: an aiosqlite-shaped connection double and an
asyncpg-shaped pool double drive read-only enforcement, parameter passthrough,
row caps, pooling reuse, and deterministic close. The friendly missing-driver
errors are forced via ``patch.dict(sys.modules, {...: None})``.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Any
from unittest import mock

import pytest

from pirn_agents.connector_base import ConnectorBase
from pirn_agents.connectors.sql_service_connector import SqlServiceConnector
from pirn_agents.credential_ref import CredentialRef


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
    """aiosqlite-shaped double recording executed queries and parameters."""

    def __init__(self, columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
        self._columns = columns
        self._rows = rows
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False

    async def execute(self, query: str, parameters: tuple[Any, ...]) -> _FakeCursor:
        self.calls.append((query, parameters))
        return _FakeCursor(self._columns, self._rows)

    async def close(self) -> None:
        self.closed = True


class _FakeRecord:
    def __init__(self, mapping: dict[str, Any]) -> None:
        self._mapping = mapping

    def keys(self) -> Sequence[str]:
        return list(self._mapping.keys())

    def values(self) -> Sequence[Any]:
        return list(self._mapping.values())


class _FakeAcquire:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    async def __aenter__(self) -> Any:
        return self._connection

    async def __aexit__(self, *_: object) -> bool:
        return False


class _FakeAsyncpgConn:
    def __init__(self, records: Sequence[_FakeRecord]) -> None:
        self._records = records
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *parameters: Any) -> Sequence[_FakeRecord]:
        self.calls.append((query, parameters))
        return self._records


class _FakeAsyncpgPool:
    def __init__(self, records: Sequence[_FakeRecord]) -> None:
        self._conn = _FakeAsyncpgConn(records)
        self.closed = False

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(self._conn)

    async def close(self) -> None:
        self.closed = True


class TestReadOnlyMode:
    async def test_select_is_allowed(self) -> None:
        conn = _FakeAiosqliteConnection(["id"], [[1], [2]])
        connector = SqlServiceConnector(connection=conn)
        columns, rows = await connector.execute("SELECT id FROM t")
        assert columns == ["id"]
        assert rows == [[1], [2]]

    async def test_write_is_rejected_in_read_only_mode(self) -> None:
        connector = SqlServiceConnector(connection=_FakeAiosqliteConnection([], []))
        with pytest.raises(ValueError, match="read-only"):
            await connector.execute("DELETE FROM t")

    async def test_write_allowed_when_read_only_disabled(self) -> None:
        conn = _FakeAiosqliteConnection(["n"], [[0]])
        connector = SqlServiceConnector(connection=conn, read_only=False)
        await connector.execute("UPDATE t SET n = 1")
        assert conn.calls[0][0] == "UPDATE t SET n = 1"


class TestParameterizationAndCaps:
    async def test_parameters_passed_through_not_interpolated(self) -> None:
        conn = _FakeAiosqliteConnection(["id"], [[1]])
        connector = SqlServiceConnector(connection=conn)
        await connector.execute("SELECT id FROM t WHERE id = ?", [42])
        assert conn.calls[0] == ("SELECT id FROM t WHERE id = ?", (42,))

    async def test_row_cap_truncates_result_set(self) -> None:
        conn = _FakeAiosqliteConnection(["id"], [[i] for i in range(10)])
        connector = SqlServiceConnector(connection=conn, max_rows=3)
        _, rows = await connector.execute("SELECT id FROM t")
        assert rows == [[0], [1], [2]]

    def test_rejects_non_positive_max_rows(self) -> None:
        with pytest.raises(ValueError, match="max_rows"):
            SqlServiceConnector(max_rows=0)

    def test_rejects_unknown_driver(self) -> None:
        with pytest.raises(ValueError, match="driver"):
            SqlServiceConnector(driver="mysql")


class TestPoolingAndLifecycle:
    async def test_single_pooled_connection_reused(self) -> None:
        conn = _FakeAiosqliteConnection(["id"], [[1]])
        connector = SqlServiceConnector(connection=conn)
        for _ in range(5):
            await connector.execute("SELECT id FROM t")
        assert await connector._get_client() is conn
        assert len(conn.calls) == 5

    async def test_close_awaits_aiosqlite_close_and_is_idempotent(self) -> None:
        conn = _FakeAiosqliteConnection([], [])
        connector = SqlServiceConnector(connection=conn)
        await connector.execute("SELECT 1")
        await connector.close()
        assert conn.closed is True
        assert connector._client is None
        await connector.close()  # no-op

    async def test_close_scrubs_credentials(self) -> None:
        connector = SqlServiceConnector(
            connection=_FakeAiosqliteConnection([], []), credential=CredentialRef("dsn")
        )
        assert connector._pirn_audit_dict()["has_credential"] is True
        await connector.close()
        assert connector._pirn_audit_dict()["has_credential"] is False

    def test_is_a_connector_base(self) -> None:
        connector = SqlServiceConnector(connection=_FakeAiosqliteConnection([], []))
        assert isinstance(connector, ConnectorBase)


class TestAsyncpgDriver:
    async def test_asyncpg_fetch_maps_records(self) -> None:
        records = [_FakeRecord({"id": 1, "name": "a"}), _FakeRecord({"id": 2, "name": "b"})]
        pool = _FakeAsyncpgPool(records)
        connector = SqlServiceConnector(driver="asyncpg", connection=pool)
        columns, rows = await connector.execute("SELECT id, name FROM t WHERE id > $1", [0])
        assert columns == ["id", "name"]
        assert rows == [[1, "a"], [2, "b"]]

    async def test_asyncpg_row_cap(self) -> None:
        records = [_FakeRecord({"id": i}) for i in range(10)]
        connector = SqlServiceConnector(
            driver="asyncpg", connection=_FakeAsyncpgPool(records), max_rows=2
        )
        _, rows = await connector.execute("SELECT id FROM t")
        assert rows == [[0], [1]]

    async def test_asyncpg_close_awaits_pool_close(self) -> None:
        pool = _FakeAsyncpgPool([])
        connector = SqlServiceConnector(driver="asyncpg", connection=pool)
        await connector.close()
        assert pool.closed is True


class TestMissingDrivers:
    async def test_missing_aiosqlite_raises_friendly_error(self) -> None:
        connector = SqlServiceConnector(database=":memory:")
        with mock.patch.dict(sys.modules, {"aiosqlite": None}):
            with pytest.raises(ImportError, match=r'pip install "pirn-agents\[sql\]"'):
                await connector.execute("SELECT 1")

    async def test_missing_asyncpg_raises_friendly_error(self) -> None:
        connector = SqlServiceConnector(driver="asyncpg", dsn="postgresql://x")
        with mock.patch.dict(sys.modules, {"asyncpg": None}):
            with pytest.raises(ImportError, match=r'pip install "pirn-agents\[postgres\]"'):
                await connector.execute("SELECT 1")
