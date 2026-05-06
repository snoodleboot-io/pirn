"""Configuration dataclass for :class:`OraclePool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class OracleConfig(ConnectionConfig):
    """Configuration for an :mod:`oracledb`-backed Oracle connection pool.

    Attributes
    ----------
    user / password:
        Login credentials.
    dsn:
        Oracle "Easy Connect" string of the form ``host:port/service``.
    wallet_location:
        Optional filesystem path to an Oracle wallet directory used for
        mTLS / TLS-only connections (e.g. Autonomous Database).
    min_size / max_size:
        Pool bounds passed to :func:`oracledb.create_pool`.
    """

    user: str | None = None
    password: str | None = None
    dsn: str | None = None
    wallet_location: str | None = None
    min_size: int = 1
    max_size: int = 4

    sensitive_fields: ClassVar[tuple[str, ...]] = ("password",)
