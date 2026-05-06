"""Configuration dataclass for :class:`AirtableClient`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class AirtableConfig(ConnectionConfig):
    """Configuration for an Airtable REST API v0 session.

    Attributes
    ----------
    api_key:
        Airtable Personal Access Token. Required.
    base_id:
        Airtable base identifier (e.g. ``appXXXXXXXXXXXXXX``). Required.
    table_name:
        Table name or table ID within the base. Required.
    page_size:
        Number of records per page (maximum 100).
    timeout:
        HTTP timeout in seconds.
    """

    api_key: str = ""
    base_id: str = ""
    table_name: str = ""
    page_size: int = 100
    timeout: float = 30.0

    sensitive_fields: ClassVar[tuple[str, ...]] = ("api_key",)
