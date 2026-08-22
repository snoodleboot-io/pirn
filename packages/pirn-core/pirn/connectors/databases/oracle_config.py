"""Configuration dataclass for :class:`OraclePool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.connectors.connection_config import ConnectionConfig
from pirn.connectors.connection_config_decorator import connection_config


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

    Notes
    -----
    There are deliberately no pool-size fields. This config drives
    :class:`~pirn.connectors.databases.oracle_pool.OraclePool`, which holds a
    single connection for its lifetime, so bounds would be inert. ``min_size``
    and ``max_size`` did exist and were passed to ``oracledb.create_pool`` —
    but that call produced a ``ConnectionPool`` with no ``cursor()``, so the
    path raised on every statement and was never reachable in practice. They
    were removed with the fix rather than left as knobs that describe a pool
    this class does not have (PIR-824). Sibling configs for genuinely pooled
    backends — MySQL, Postgres, MSSQL — keep theirs.
    """

    user: str | None = None
    password: str | None = None
    dsn: str | None = None
    wallet_location: str | None = None

    sensitive_fields: ClassVar[tuple[str, ...]] = ("password",)
