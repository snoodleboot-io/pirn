"""Configuration dataclass for :class:`DatabricksPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class DatabricksConfig(ConnectionConfig):
    """Configuration for a Databricks SQL connection.

    Attributes
    ----------
    server_hostname:
        Workspace hostname (e.g. ``adb-1234567890.0.azuredatabricks.net``).
    http_path:
        Path component for the SQL warehouse / cluster (e.g.
        ``/sql/1.0/warehouses/abcd1234``).
    access_token:
        Personal-access or service-principal token. Sensitive — redacted
        in repr/audit output.
    catalog / schema:
        Optional default Unity Catalog context.
    """

    server_hostname: str | None = None
    http_path: str | None = None
    access_token: str | None = None
    catalog: str | None = None
    schema: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ()
