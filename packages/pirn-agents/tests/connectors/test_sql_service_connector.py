"""Tests for :class:`SqlServiceConnector` over an offline column-aware pool double.

The connector is now a thin layer over a core-backed :class:`ColumnAwarePool`
(pooling, credential scrub, and injection guard come from core's pools). These
tests inject a fake pool and cover the three things the connector adds — read-only
enforcement, parameter passthrough, and the row cap — plus deterministic close.
The friendly missing-driver errors are forced via ``patch.dict(sys.modules, ...)``.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Any
from unittest import mock

import pytest
from pirn.connectors.connector_base import ConnectorBase
from pirn.security.credential_ref import CredentialRef

from pirn_agents.connectors.column_aware_pool import ColumnAwarePool
from pirn_agents.connectors.sql_service_connector import SqlServiceConnector


class _FakePool(ColumnAwarePool):
    """Offline ColumnAwarePool double recording queries; returns fixed columns/rows."""

    def __init__(self, columns: Sequence[str] = (), rows: Sequence[Sequence[Any]] = ()) -> None:
        self._columns = list(columns)
        self._rows = [list(row) for row in rows]
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False

    async def fetch_columns(
        self, query: str, parameters: Sequence[Any] | None = None
    ) -> tuple[list[str], list[list[Any]]]:
        self.calls.append((query, tuple(parameters or ())))
        return self._columns, [list(row) for row in self._rows]

    async def close(self) -> None:
        self.closed = True


class TestReadOnlyMode:
    async def test_select_is_allowed(self) -> None:
        connector = SqlServiceConnector(pool=_FakePool(["id"], [[1], [2]]))
        columns, rows = await connector.execute("SELECT id FROM t")
        assert columns == ["id"]
        assert rows == [[1], [2]]

    async def test_write_is_rejected_in_read_only_mode(self) -> None:
        connector = SqlServiceConnector(pool=_FakePool())
        with pytest.raises(ValueError, match="read-only"):
            await connector.execute("DELETE FROM t")

    async def test_write_allowed_when_read_only_disabled(self) -> None:
        pool = _FakePool(["n"], [[0]])
        connector = SqlServiceConnector(pool=pool, read_only=False)
        await connector.execute("UPDATE t SET n = 1")
        assert pool.calls[0][0] == "UPDATE t SET n = 1"


class TestWritePersistence:
    """Regression (PIR-801): ``read_only=False`` writes must actually persist.

    ``execute`` routes through ``ColumnAwarePool.fetch_columns``, which issued no
    commit, so an ``INSERT`` reported success, read back correctly *within the same
    session*, and then vanished when the connection closed — with no error at any
    point. These tests run a real aiosqlite file database so the close/reopen
    boundary is exercised for real; an in-memory database would be destroyed on
    close and could not tell the two outcomes apart.
    """

    async def test_a_write_survives_close_and_reopen(self, tmp_path: Any) -> None:
        pytest.importorskip("aiosqlite")
        database = str(tmp_path / "persist.db")

        writer = SqlServiceConnector(driver="aiosqlite", database=database, read_only=False)
        try:
            await writer.execute("CREATE TABLE widget (id INTEGER PRIMARY KEY, name TEXT)")
            await writer.execute("INSERT INTO widget (id, name) VALUES (?, ?)", (1, "sprocket"))
            _, same_session = await writer.execute("SELECT id, name FROM widget")
            assert same_session == [[1, "sprocket"]]
        finally:
            await writer.close()

        reader = SqlServiceConnector(driver="aiosqlite", database=database)
        try:
            columns, rows = await reader.execute("SELECT id, name FROM widget")
        finally:
            await reader.close()
        assert columns == ["id", "name"]
        assert rows == [[1, "sprocket"]]

    async def test_an_update_and_delete_survive_close_and_reopen(self, tmp_path: Any) -> None:
        pytest.importorskip("aiosqlite")
        database = str(tmp_path / "mutate.db")

        writer = SqlServiceConnector(driver="aiosqlite", database=database, read_only=False)
        try:
            await writer.execute("CREATE TABLE widget (id INTEGER PRIMARY KEY, name TEXT)")
            await writer.execute("INSERT INTO widget (id, name) VALUES (?, ?)", (1, "old"))
            await writer.execute("INSERT INTO widget (id, name) VALUES (?, ?)", (2, "doomed"))
            await writer.execute("UPDATE widget SET name = ? WHERE id = ?", ("new", 1))
            await writer.execute("DELETE FROM widget WHERE id = ?", (2,))
        finally:
            await writer.close()

        reader = SqlServiceConnector(driver="aiosqlite", database=database)
        try:
            _, rows = await reader.execute("SELECT id, name FROM widget ORDER BY id")
        finally:
            await reader.close()
        assert rows == [[1, "new"]]

    async def test_read_only_still_refuses_writes_against_a_live_backend(
        self, tmp_path: Any
    ) -> None:
        # The commit added for PIR-801 must not open a write path in read-only
        # mode: the guard still rejects before the pool is ever reached.
        pytest.importorskip("aiosqlite")
        database = str(tmp_path / "guarded.db")

        writer = SqlServiceConnector(driver="aiosqlite", database=database, read_only=False)
        try:
            await writer.execute("CREATE TABLE widget (id INTEGER PRIMARY KEY, name TEXT)")
            await writer.execute("INSERT INTO widget (id, name) VALUES (?, ?)", (1, "kept"))
        finally:
            await writer.close()

        reader = SqlServiceConnector(driver="aiosqlite", database=database, read_only=True)
        try:
            with pytest.raises(ValueError, match="read-only"):
                await reader.execute("DELETE FROM widget")
            _, rows = await reader.execute("SELECT id, name FROM widget")
        finally:
            await reader.close()
        assert rows == [[1, "kept"]]


class TestParameterizationAndCaps:
    async def test_parameters_passed_through_not_interpolated(self) -> None:
        pool = _FakePool(["id"], [[1]])
        connector = SqlServiceConnector(pool=pool)
        await connector.execute("SELECT id FROM t WHERE id = ?", [42])
        assert pool.calls[0] == ("SELECT id FROM t WHERE id = ?", (42,))

    async def test_row_cap_truncates_result_set(self) -> None:
        pool = _FakePool(["id"], [[i] for i in range(10)])
        connector = SqlServiceConnector(pool=pool, max_rows=3)
        _, rows = await connector.execute("SELECT id FROM t")
        assert rows == [[0], [1], [2]]

    def test_rejects_non_positive_max_rows(self) -> None:
        with pytest.raises(ValueError, match="max_rows"):
            SqlServiceConnector(max_rows=0)

    def test_rejects_unknown_driver(self) -> None:
        with pytest.raises(ValueError, match="driver"):
            SqlServiceConnector(driver="mysql")


class TestPoolingAndLifecycle:
    async def test_single_pooled_pool_reused(self) -> None:
        pool = _FakePool(["id"], [[1]])
        connector = SqlServiceConnector(pool=pool)
        for _ in range(5):
            await connector.execute("SELECT id FROM t")
        assert await connector._get_client() is pool
        assert len(pool.calls) == 5

    async def test_close_awaits_pool_close_and_is_idempotent(self) -> None:
        pool = _FakePool()
        connector = SqlServiceConnector(pool=pool)
        await connector.execute("SELECT 1")
        await connector.close()
        assert pool.closed is True
        assert connector._client is None
        await connector.close()  # no-op

    async def test_close_scrubs_credentials(self) -> None:
        connector = SqlServiceConnector(pool=_FakePool(), credential=CredentialRef("dsn"))
        assert connector._pirn_audit_dict()["has_credential"] is True
        await connector.close()
        assert connector._pirn_audit_dict()["has_credential"] is False

    def test_is_a_connector_base(self) -> None:
        connector = SqlServiceConnector(pool=_FakePool())
        assert isinstance(connector, ConnectorBase)


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
