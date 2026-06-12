"""Configuration dataclass for :class:`CosmosDBPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class CosmosDBConfig(ConnectionConfig):
    """Configuration for an Azure Cosmos DB connection.

    ``endpoint`` is required and must be non-empty.
    """

    endpoint: str = ""
    key: str = ""
    database: str = ""
    container: str = ""
    connection_mode: str = "gateway"
    max_retry_attempts: int = 3

    sensitive_fields: ClassVar[tuple[str, ...]] = ("key",)

    def __post_init__(self) -> None:
        if not self.endpoint:
            raise ValueError("CosmosDBConfig: endpoint must be non-empty")
