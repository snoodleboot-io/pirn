"""Unit tests for :class:`MemgraphPool`.

Uses injected stubs — no real Memgraph instance required. Integration tests
live under ``tests/integration`` behind the ``needs_memgraph`` marker.
"""

from __future__ import annotations

import logging
import unittest
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.graph.memgraph_config import MemgraphConfig
from pirn.connectors.graph.memgraph_pool import MemgraphPool

# ──────────────────────────────────────────────────────────────── fakes


class FakeMemgraphRecord:
    """Represents a single result row returned by the fake connection."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __iter__(self):  # type: ignore[override]
        return iter(self._data.items())

    def keys(self):  # type: ignore[return]
        return self._data.keys()

    def values(self):  # type: ignore[return]
        return self._data.values()

    def __getitem__(self, key: str) -> Any:
        return self._data[key]


class FakeMemgraphConnection:
    """Mirrors the gqlalchemy Memgraph connection surface used by MemgraphPool."""

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self.executed: list[tuple[str, Any]] = []
        self._records = records or []
        self.closed = False

    async def execute(self, query: str, parameters: Any = None) -> list[FakeMemgraphRecord]:
        self.executed.append((query, parameters))
        return [FakeMemgraphRecord(r) for r in self._records]

    async def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.IsolatedAsyncioTestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool = MemgraphPool(connection=FakeMemgraphConnection())
        assert isinstance(pool, DatabaseConnectionPool)
    
    
    def test_construction_requires_config_or_connection(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or connection="):
            MemgraphPool()
    
    
# ────────────────────────────────────────────────────────────── delegation


class TestDelegation(unittest.IsolatedAsyncioTestCase):
    async def test_execute_passes_query_and_params(self) -> None:
        fake = FakeMemgraphConnection()
        pool = MemgraphPool(connection=fake)
        await pool.execute("CREATE (n:Node {id: $id})", {"id": 42})
        assert fake.executed == [("CREATE (n:Node {id: $id})", {"id": 42})]

    async def test_execute_no_params(self) -> None:
        fake = FakeMemgraphConnection()
        pool = MemgraphPool(connection=fake)
        await pool.execute("MATCH (n) DETACH DELETE n")
        assert fake.executed == [("MATCH (n) DETACH DELETE n", None)]

    async def test_fetch_all_returns_list_of_dicts(self) -> None:
        records = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        fake = FakeMemgraphConnection(records=records)
        pool = MemgraphPool(connection=fake)
        result = await pool.fetch_all("MATCH (n) RETURN n")
        assert result == records

    async def test_execute_many_runs_each_item(self) -> None:
        fake = FakeMemgraphConnection()
        pool = MemgraphPool(connection=fake)
        await pool.execute_many(
            "CREATE (n:Node {id: $id})",
            [{"id": 1}, {"id": 2}],
        )
        assert len(fake.executed) == 2

    async def test_acquire_returns_connection(self) -> None:
        fake = FakeMemgraphConnection()
        pool = MemgraphPool(connection=fake)
        conn = await pool.acquire()
        assert conn is fake

    async def test_release_is_noop(self) -> None:
        fake = FakeMemgraphConnection()
        pool = MemgraphPool(connection=fake)
        conn = await pool.acquire()
        await pool.release(conn)
        assert not fake.closed


# ─────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_connection(self) -> None:
        fake = FakeMemgraphConnection()
        pool = MemgraphPool(connection=fake)
        await pool.close()
        assert fake.closed is True

    async def test_acquire_after_close_raises(self) -> None:
        pool = MemgraphPool(connection=FakeMemgraphConnection())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()

    async def test_close_clears_credentials(self) -> None:
        pool = MemgraphPool(config=MemgraphConfig(), connection=FakeMemgraphConnection())
        assert pool._config is not None
        await pool.close()
        assert pool._config is None

    async def test_use_after_close_raises(self) -> None:
        pool = MemgraphPool(config=MemgraphConfig(), connection=FakeMemgraphConnection())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()


# ──────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_password(self) -> None:
        cfg = MemgraphConfig(password="my-secret-pw")
        assert "my-secret-pw" not in repr(cfg)
        assert "<redacted>" in repr(cfg)

    def test_audit_dict_redacts_password(self) -> None:
        cfg = MemgraphConfig(password="my-secret-pw")
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"
        assert "my-secret-pw" not in str(d)

    def test_repr_shows_host_and_port(self) -> None:
        cfg = MemgraphConfig(host="memgraph.example.com", port=7687)
        text = repr(cfg)
        assert "memgraph.example.com" in text
        assert "7687" in text


# ────────────────────────────────────────────────────────────── log events


class TestLogEvents(unittest.IsolatedAsyncioTestCase):
    async def test_close_emits_debug_log(self) -> None:
        pool = MemgraphPool(connection=FakeMemgraphConnection())
        with self.assertLogs("pirn", level=logging.DEBUG) as cm:
            await pool.close()
        assert any("memgraph.close" in msg for msg in cm.output)
