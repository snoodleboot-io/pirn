"""Configuration dataclass for :class:`KdbPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class KdbConfig(ConnectionConfig):
    """Configuration for a kdb+ connection.

    Uses ``pykx`` (preferred) or ``qpython`` (legacy) under the hood, both
    wrapped in ``asyncio.to_thread`` for async compatibility.
    """

    host: str = "localhost"
    port: int = 5000
    username: str = ""
    password: str = ""
    timeout: float = 30.0
    tls: bool = False

    sensitive_fields: ClassVar[tuple[str, ...]] = ("password",)
