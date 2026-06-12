"""Configuration dataclass for :class:`AzureServiceBusBroker`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class AzureServiceBusConfig(ConnectionConfig):
    """Configuration for an Azure Service Bus broker."""

    connection_string: str | None = None
    namespace: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ("connection_string",)
