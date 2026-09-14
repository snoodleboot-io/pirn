# pyright: reportUnnecessaryIsInstance=false
# runtime-bound inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""Async Azure Cosmos DB pool backed by :mod:`azure.cosmos.aio`."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.document.cosmosdb_config import CosmosDBConfig
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.connectors.payload_shape import PayloadShape
from pirn.core.optional_dependency import OptionalDependency


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
        self._container: Any = container_client
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

    async def execute(self, query: str, parameters: Iterable[Any] | None = None) -> str:
        """Upsert an item; ``parameters`` is the item dict. Returns item id."""
        await self._ensure_container()
        if self._container is None:
            raise RuntimeError("CosmosDBPool: not connected — call connect() first")
        item: Iterable[Any] = parameters if parameters is not None else {}
        result = await self._container.upsert_item(item)
        return str(result.get("id", ""))

    async def fetch_all(self, query: str, parameters: Iterable[Any] | None = None) -> list[Any]:
        """Execute a SQL query against the container and return all items."""
        await self._ensure_container()
        if self._container is None:
            raise RuntimeError("CosmosDBPool: not connected — call connect() first")
        return [
            item
            async for item in self._container.query_items(
                query=query,
                enable_cross_partition_query=True,
            )
        ]

    async def execute_many(self, query: str, parameter_seq: Iterable[Iterable[Any]]) -> None:
        """Upsert each item dict yielded by parameter_seq."""
        await self._ensure_container()
        if self._container is None:
            raise RuntimeError("CosmosDBPool: not connected — call connect() first")
        for row in parameter_seq:
            empty: dict[str, object] = {}
            item: object = (
                row if PayloadShape.is_str_dict(row) else (next(iter(row), empty) if row else empty)
            )
            await self._container.upsert_item(item)

    async def _ensure_container(self) -> None:
        if self._closed:
            raise self._closed_error("CosmosDBPool")
        if self._container is None:
            await self._create_container()

    async def _create_container(self) -> None:
        cosmos_aio = OptionalDependency.require("azure.cosmos.aio", extra="cosmosdb")
        if self._config is None:
            raise self._missing_config_error("CosmosDBPool", "container_client")

        try:
            self._cosmos_client = cosmos_aio.CosmosClient(
                url=self._config.endpoint,
                credential=self._config.key,
                connection_mode=self._config.connection_mode,
            )
            db_client = self._cosmos_client.get_database_client(self._config.database)
            self._container = db_client.get_container_client(self._config.container)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("cosmosdb.connect")
