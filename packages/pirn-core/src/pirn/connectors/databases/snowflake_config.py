"""Configuration dataclass for :class:`SnowflakePool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class SnowflakeConfig(ConnectionConfig):
    """Configuration for a Snowflake connection.

    Attributes
    ----------
    account:
        Snowflake account identifier (e.g. ``xy12345.us-east-1``).
    user / password:
        Login credentials.
    warehouse / database / schema / role:
        Default session context applied to every query.
    """

    account: str | None = None
    user: str | None = None
    password: str | None = None
    warehouse: str | None = None
    database: str | None = None
    schema: str | None = None
    role: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ()
