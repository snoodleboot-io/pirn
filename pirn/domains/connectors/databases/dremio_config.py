"""Configuration dataclass for :class:`DremioPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class DremioConfig(ConnectionConfig):
    """Configuration for a Dremio Arrow Flight SQL connection.

    Attributes
    ----------
    host:
        Dremio server hostname.
    port:
        Arrow Flight gRPC port (default 32010).
    username:
        Dremio username.
    password:
        Dremio password. Sensitive — redacted in repr.
    tls:
        Whether to use TLS for the Flight connection.
    path:
        Dremio project or space path.
    connection_timeout:
        Connection timeout in seconds.
    """

    host: str = "localhost"
    port: int = 32010
    username: str = "dremio"
    password: str = ""
    tls: bool = False
    path: str = "/"
    connection_timeout: float = 30.0

    sensitive_fields: ClassVar[tuple[str, ...]] = ("password",)
