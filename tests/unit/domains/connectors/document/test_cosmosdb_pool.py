"""Unit tests for :class:`CosmosDBPool`.

Uses injected fakes — no real Azure Cosmos DB or azure-cosmos needed.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.document.cosmosdb_config import CosmosDBConfig
from pirn.domains.connectors.document.cosmosdb_pool import CosmosDBPool


# ──────────────────────────────────────────────────────────── fakes


class FakeCosmosContainer:
    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self._items = items or []
        self.upserted: list[Any] = []
        self.closed = False

    async def upsert_item(self, item: Any) -> dict[str, Any]:
        self.upserted.append(item)
        result = dict(item)
        if "id" not in result:
            result["id"] = "generated-id"
        return result

    async def query_items(
        self, query: str, enable_cross_partition_query: bool = False
    ) -> AsyncIterator[dict[str, Any]]:
        for item in self._items:
            yield item

    async def close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── helpers


def make_pool(
    items: list[dict[str, Any]] | None = None,
) -> tuple[CosmosDBPool, FakeCosmosContainer]:
    config = CosmosDBConfig(
        endpoint="https://account.documents.azure.com:443/",
        database="testdb",
        container="testcontainer",
    )
    fake_container = FakeCosmosContainer(items)
    pool = CosmosDBPool(config=config, container_client=fake_container)
    return pool, fake_container


# ───────────────────────────────────────────────────────────── conformance


def test_implements_database_connection_pool() -> None:
    pool, _ = make_pool()
    assert isinstance(pool, DatabaseConnectionPool)


def test_construction_requires_config_or_container_client() -> None:
    with pytest.raises(TypeError, match="config= or container_client="):
        CosmosDBPool()


def test_config_requires_non_empty_endpoint() -> None:
    with pytest.raises(ValueError, match="endpoint must be non-empty"):
        CosmosDBConfig(endpoint="")


# ───────────────────────────────────────────────────────────── operations


@pytest.mark.asyncio
class TestOperations:
    async def test_execute_upserts_item(self) -> None:
        pool, fake_container = make_pool()
        item = {"id": "item-001", "name": "Alice"}
        result = await pool.execute("ignored", item)
        assert result == "item-001"
        assert fake_container.upserted == [item]

    async def test_execute_returns_generated_id_when_missing(self) -> None:
        pool, _ = make_pool()
        result = await pool.execute("ignored", {"name": "NoId"})
        assert result == "generated-id"

    async def test_fetch_all_returns_items(self) -> None:
        items = [{"id": "1", "val": 10}, {"id": "2", "val": 20}]
        pool, _ = make_pool(items)
        result = await pool.fetch_all("SELECT * FROM c")
        assert result == items

    async def test_execute_many_upserts_each(self) -> None:
        pool, fake_container = make_pool()
        items = [{"id": "a", "x": 1}, {"id": "b", "x": 2}]
        await pool.execute_many("ignored", items)
        assert fake_container.upserted == items

    async def test_acquire_returns_container(self) -> None:
        pool, fake_container = make_pool()
        container = await pool.acquire()
        assert container is fake_container

    async def test_release_is_noop(self) -> None:
        pool, _ = make_pool()
        container = await pool.acquire()
        await pool.release(container)  # should not raise


# ───────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_marks_pool_closed(self) -> None:
        pool, _ = make_pool()
        await pool.close()
        assert pool._closed is True

    async def test_acquire_after_close_raises(self) -> None:
        pool, _ = make_pool()
        await pool.close()
        with pytest.raises(RuntimeError, match="closed"):
            await pool.acquire()


# ───────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
    def test_repr_redacts_key(self) -> None:
        cfg = CosmosDBConfig(
            endpoint="https://account.documents.azure.com:443/",
            key="my-master-key-secret",
        )
        text = repr(cfg)
        assert "my-master-key-secret" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_key(self) -> None:
        cfg = CosmosDBConfig(
            endpoint="https://account.documents.azure.com:443/",
            key="s3cr3t",
        )
        d = cfg.to_audit_dict()
        assert d["key"] == "<redacted>"
