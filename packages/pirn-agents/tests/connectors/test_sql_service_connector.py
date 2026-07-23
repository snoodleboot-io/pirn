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

from pirn_agents.connector_base import ConnectorBase
from pirn_agents.connectors.column_aware_pool import ColumnAwarePool
from pirn_agents.connectors.sql_service_connector import SqlServiceConnector
from pirn_agents.credential_ref import CredentialRef


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
