"""Async Azure Cosmos DB pool backed by :mod:`azure.cosmos.aio`."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.document.cosmosdb_config import CosmosDBConfig
from pirn.domains.connectors.dsn_scrubber import DsnScrubber


class CosmosDBPool(DatabaseConnectionPool):
    """Async Azure Cosmos DB pool using azure-cosmos aio client."""

    def __init__(
        self,
        config: CosmosDBConfig | None = None,
        *,
        container_client: Any = None,
    ) -> None:
        if config is None and container_client is None:
            raise TypeError("CosmosDBPool requires either config= or container_client=")
        if config is not None and not isinstance(config, CosmosDBConfig):
            raise TypeError(
                f"CosmosDBPool: config must be CosmosDBConfig, got {type(config).__name__}"
            )
        self._config = config
        self._container = container_client
        self._cosmos_client: Any = None
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> CosmosDBConfig | None:
        return self._config

    async def acquire(self) -> Any:
        await self._ensure_container()
        return self._container

    async def release(self, connection: Any) -> None:
        pass  # azure-cosmos aio manages connections internally

    async def close(self) -> None:
        if self._cosmos_client is not None:
            await self._cosmos_client.close()
            self._cosmos_client = None
        self._container = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("cosmosdb.close")

    async def execute(self, query: str, *args: Any) -> str:
        """Upsert an item; ``args[0]`` is the item dict. Returns item id."""
        await self._ensure_container()
        item = args[0] if args else {}
        result = await self._container.upsert_item(item)
        return str(result.get("id", ""))

    async def fetch_all(self, query: str, *args: Any) -> list[Any]:
        """Execute a SQL query against the container and return all items."""
        await self._ensure_container()
        return [
            item
            async for item in self._container.query_items(
                query=query,
                enable_cross_partition_query=True,
            )
        ]

    async def execute_many(self, query: str, args_seq: Iterable[Iterable[Any]]) -> None:
        """Upsert each item dict yielded by args_seq."""
        await self._ensure_container()
        for args in args_seq:
            item = args if isinstance(args, dict) else (next(iter(args)) if args else {})
            await self._container.upsert_item(item)

    async def _ensure_container(self) -> None:
        if self._closed:
            raise RuntimeError("CosmosDBPool is closed")
        if self._container is None:
            await self._create_container()

    async def _create_container(self) -> None:
        try:
            from azure.cosmos.aio import CosmosClient
        except ImportError as exc:
            raise ImportError(
                "CosmosDBPool requires azure-cosmos; install via pip install pirn[cosmosdb]"
            ) from exc
        if self._config is None:
            raise RuntimeError("CosmosDBPool: missing config and no injected container_client")

        try:
            self._cosmos_client = CosmosClient(
                url=self._config.endpoint,
                credential=self._config.key,
                connection_mode=self._config.connection_mode,
            )
            db_client = self._cosmos_client.get_database_client(self._config.database)
            self._container = db_client.get_container_client(self._config.container)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("cosmosdb.connect")
